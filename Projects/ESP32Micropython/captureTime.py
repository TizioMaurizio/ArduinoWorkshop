import camera
import os
import utime
import machine
import _thread
n = 0

def cap():
    global n
    n = n + 1
    buf = camera.capture()
    return buf

def test():
    begin = utime.ticks_ms()
    time = utime.ticks_ms()
    camera.init(1)
    i = 0
    while(time - begin < 3000):
        buf = camera.capture()
        i = i + 1
        time = utime.ticks_ms()
    camera.deinit()
    print('Took', i, ' pictures')


def testThread():
    begin = utime.ticks_ms()
    time = utime.ticks_ms()
    camera.init(1)
    i = 0
    while(time - begin < 3000):
        if(n<5):
            _thread.start_new_thread(cap, ())
        else:
            pass
        i = i + 1
        time = utime.ticks_ms()
    machine.sleep(500)
    camera.deinit()
    print('Took', i, ' pictures')
