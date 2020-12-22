# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
import webrepl
webrepl.start()

import wifiConnect
#wifiConnect.connect('TIM-37482183', 'HnbD76SPtLs7G8vS') #if network not found start Access Point mode
wifiConnect.connect('RedmiMau', 'mau12397') #if network not found start Access Point mode

import machine
import os
try:
    uos.mount(machine.SDCard(), "/sd")
    os.chdir("sd")
except:
    print("could not mount SD card")
