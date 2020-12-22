import socket
import _thread
import utime
import servoDrive
from servoDrive import jsonPoses
import sys
servoDrive.INTERVAL = 10
host = ''
port = 5555
RECTIME = 20
RECSIZE = 128
STOP = 0
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((host, port))
values = []
rotation = [0, 0, 0]

def getValue():
    global values, s, rotation
    prevTime = 0
    while not STOP:
        try:
            currentTime = utime.ticks_ms()
            if (currentTime - prevTime >= RECTIME):
                prevTime = currentTime
                message, address = s.recvfrom(RECSIZE)
                #currentTime = utime.ticks_ms()
                values = str(message).split(',')
                rotation[0] = float(values[14])
                rotation[1] = float(values[15])
                rotation[2] = str(values[16])
                if (rotation[0] >= 90) and (rotation[0] <= 270):
                    #drive.setangle(1, int((rotation[0]-180)))
                    jsonPoses[1] = max(-90, min(int(rotation[1]), 90))
                    jsonPoses[2] = 30 #(rotation[2].replace('\'', ''))
                    jsonPoses[3] = 1
                    jsonPoses[4] = max(-90, min(int(-((rotation[0])-180)), 90))
                if(currentTime - prevTime >= 2000):
                    #prevTime = currentTime
                    #print(rotation)
                    pass
                else:
                    pass
        except:
            currentTime = utime.ticks_ms()
            if (currentTime - prevTime >= 2000):
                prevTime = currentTime
                print('e')#, rotation)
    print('Terminating sensorReceiver.getValue()')
    #del sys.modules['sensorReceiver']

def deimport():
    global STOP
    STOP = 1
    servoDrive.stop()
    del sys.modules['sensorReceiver']
    print('sensorReceiver.getValue() thread will terminate at next udp packet received')

_thread.start_new_thread(getValue, ())
