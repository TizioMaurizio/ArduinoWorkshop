import machine

p = machine.Pin(13, machine.Pin.OUT)

def setLed(value):
    global p
    p.value(value)


# Complete project details at https://RandomNerdTutorials.com
try:
    import pca9865

    SDA = 16
    SCL = 0
    drive = pca9865.pca9865(SDA, SCL)
    drive.alloff()
except:
    pass

import webrepl

webrepl.start()

import network

import esp

esp.osdebug(None)

import wifiConnect

wifiConnect.connect('TIM-37482183', 'HnbD76SPtLs7G8vS')  # if network not found start Access Point mode

import uos
import machine
import time


def start_blinking():
    import machine
    import utime
    print('blink begin')
    p = machine.Pin(13, machine.Pin.OUT)
    blink = 1
    prev = utime.ticks_ms()
    while True:
        time = utime.ticks_ms()
        if ((time - prev) > 1000):
            p.value(1)
            blink = blink + 1
            time.sleep(200)
            p.value(0)
            blink = blink + 1
            prev = utime.ticks_ms()


time.sleep(0.5)
try:
    uos.mount(machine.SDCard(), "/sd")
    uos.chdir("/sd")
except:
    print("could not mount SD card")
    import _thread

    print('starting to blink')
    _thread.start_new_thread(start_blinking, ())

print(uos.listdir())

