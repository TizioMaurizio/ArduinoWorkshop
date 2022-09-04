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
    camera.framesize(camera.FRAME_QVGA)
# The options are the following:
# FRAME_96X96 FRAME_QQVGA FRAME_QCIF FRAME_HQVGA FRAME_240X240
# FRAME_QVGA FRAME_CIF FRAME_HVGA FRAME_VGA FRAME_SVGA
# FRAME_XGA FRAME_HD FRAME_SXGA FRAME_UXGA FRAME_FHD
# FRAME_P_HD FRAME_P_3MP FRAME_QXGA FRAME_QHD FRAME_WQXGA
# FRAME_P_FHD FRAME_QSXGA
# Check this link for more information: https://bit.ly/2YOzizz
    camera.quality(10)
    i = 0
    TIME = 3000
    while(time - begin < TIME):
        cap()
        i = i + 1
        time = utime.ticks_ms()
    machine.sleep(500)
    camera.deinit()
    print('Took', i, ' pictures in',TIME/1000,'seconds')

def stream():
    import socket
    host = ''
    port = 5555
    RECTIME = 20
    RECSIZE = 256  # check this if jsons don't work
    STOP = 0
    RECEIVER = socket.getaddrinfo('DESKTOP-UEIIPLJ', 80)[0][-1][0]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))

    begin = utime.ticks_ms()
    time = utime.ticks_ms()
    camera.init(1)
    camera.framesize(camera.FRAME_QVGA)
# The options are the following:
# FRAME_96X96 FRAME_QQVGA FRAME_QCIF FRAME_HQVGA FRAME_240X240
# FRAME_QVGA FRAME_CIF FRAME_HVGA FRAME_VGA FRAME_SVGA
# FRAME_XGA FRAME_HD FRAME_SXGA FRAME_UXGA FRAME_FHD
# FRAME_P_HD FRAME_P_3MP FRAME_QXGA FRAME_QHD FRAME_WQXGA
# FRAME_P_FHD FRAME_QSXGA
# Check this link for more information: https://bit.ly/2YOzizz
    camera.quality(10)
    i = 0
    while(True):
        i= i+1
        s.sendto(cap(), (RECEIVER, 5555))
        print(i)
        time = utime.ticks_ms()
    machine.sleep(500)
    camera.deinit()
    print('Stream finished')
