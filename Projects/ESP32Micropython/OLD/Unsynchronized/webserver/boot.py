# Complete project details at https://RandomNerdTutorials.com

import webrepl
webrepl.start()

import network

import esp
esp.osdebug(None)

import wifiConnect
wifiConnect.connect('TIM-37482183', 'HnbD76SPtLs7G8vS') #if network not found start Access Point mode

import uos
import machine
import time

time.sleep(0.5)
try:
    uos.mount(machine.SDCard(), "/sd")
    uos.chdir("sd")
except:
    print("could not mount SD card")
print(uos.listdir())
