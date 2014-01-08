#!/usr/bin/python2.7
#Code fixed from http://www.linuxuser.co.uk/tutorials/emulate-a-bluetooth-keyboard-with-the-raspberry-pi

import os
import sys
import bluetooth
from bluetooth import *
import dbus
import time
import evdev
from evdev import *
import keymap

class Bluetooth:
  P_CTRL = 17
  P_INTR = 19

  HOST = 0
  PORT = 1

  def __init__(self):
    os.system("hciconfig hci0 class 0x002540")
    os.system("hciconfig hci0 name Raspberry\ Pi")
    os.system("hciconfig hci0 piscan")
    self.scontrol = BluetoothSocket(L2CAP)
    self.sinterrupt = BluetoothSocket(L2CAP)
    self.scontrol.bind(("", Bluetooth.P_CTRL))
    self.sinterrupt.bind(("", Bluetooth.P_INTR))
    self.bus = dbus.SystemBus()

    self.manager = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.bluez.Manager")
    adapter_path = self.manager.DefaultAdapter()
    self.service = dbus.Interface(self.bus.get_object("org.bluez", adapter_path), "org.bluez.Service")

    with open(sys.path[0] + "/sdp_record.xml", "r") as fh:
      self.service_record = fh.read()

  def listen(self):
    self.service_handle = self.service.AddRecord(self.service_record)
    print "Service record added"
    self.scontrol.listen(1) # Limit of 1 connection
    self.sinterrupt.listen(1)
    print "Waiting for a connection"
    self.ccontrol, self.cinfo = self.scontrol.accept()
    print "Got a connection on the control channel from " + self.cinfo[Bluetooth.HOST]
    self.cinterrupt, self.cinfo = self.sinterrupt.accept()
    print "Got a connection on the interrupt channel fro " + self.cinfo[Bluetooth.HOST]

  def send_input(self, ir):
    #  Convert the hex array to a string
    hex_str = ""
    for element in ir:
      if type(element) is list:
        # This is our bit array - convrt it to a single byte represented
        # as a char
        bin_str = ""
        for bit in element:
          bin_str += str(bit)
        hex_str += chr(int(bin_str, 2))
      else:
        # This is a hex value - we can convert it straight to a char
        hex_str += chr(element)
    # Send an input report
    self.cinterrupt.send(hex_str)

class Keyboard():
  def __init__(self):
    # The structure for an bt keyboard input report (size is 10 bytes)
    self.state = [
         0xA1, # This is an input report
         0x01, # Usage report = Keyboard
         # Bit array for Modifier keys
         [0,   # Right GUI - (usually the Windows key)
          0,   # Right ALT
          0,   # Right Shift
          0,   # Right Control
          0,   # Left GUI - (again, usually the Windows key)
          0,   # Left ALT
          0,   # Left Shift
          0],   # Left Control
         0x00,  # Vendor reserved
         0x00,  # Rest is space for 6 keys
         0x00,
         0x00,
         0x00,
         0x00,
         0x00 ]

    # Keep trying to get a keyboard
    have_dev = False
    while have_dev == False:
      try:
        # Try and get a keyboard - should always be event0 as we.re only
        # plugging one thing in
        self.dev = InputDevice("/dev/input/event0")
        have_dev = True
      except OSError:
        print "Keyboard not found, waiting 3 seconds and retrying"
        time.sleep(3)
      print "Found a keyboard"

  def change_state(self, event):
    evdev_code = ecodes.KEY[event.code]
    modkey_element = keymap.modkey(evdev_code)
    if modkey_element > 0:
      # Need to set one of the modifier bits
      if self.state[2][modkey_element] == 0:
        self.state[2][modkey_element] = 1
      else:
        self.state[2][modkey_element] = 0
    else:
      # Get the hex keycode of the key
      hex_key = keymap.convert(evdev_code)
      # Loop through elements 4 to 9 of the input report structure
      for i in range (4, 10):
        if self.state[i] == hex_key and event.value == 0:
          # Code is 0 so we need to depress it
          self.state[i] = 0x00
          break
        elif self.state[i] == 0x00 and event.value == 1:
          # If the current space is empty and the key is being pressed
          self.state[i] = hex_key
          break

  def event_loop(self, bt):
    for event in self.dev.read_loop():
      # Only bother if we hit a key and it's an up or down event
      if event.type == ecodes.EV_KEY and event.value < 2:
        self.change_state(event)
        bt.send_input(self.state)

if __name__ == "__main__":
  if not os.geteuid() == 0:
    sys.exit("Only root can run this script")
  bt = Bluetooth()
  bt.listen()
  kb = Keyboard()
  kb.event_loop(bt)