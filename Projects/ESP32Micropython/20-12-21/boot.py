# Complete project details at https://RandomNerdTutorials.com

import webrepl
webrepl.start()

import time

try:
  import usocket as socket
except:
  import socket

from machine import Pin
import network

import esp
esp.osdebug(None)

import gc
gc.collect()

#ssid = 'TIM-37482183'
#password = 'HnbD76SPtLs7G8vS'
ssid = 'RedmiMau'
password = 'mau12397'

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)

while station.isconnected() == False:
  pass

print('Connection successful')
print(station.ifconfig())

led = Pin(2, Pin.OUT)

time.sleep(0.5)

import uos

try:
    uos.mount(machine.SDCard(), "/sd")
    uos.chdir("sd")
except:
    print("could not mount SD card")