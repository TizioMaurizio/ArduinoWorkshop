import socket
import _thread
import utime
import pca9865
from servoDrive import targetPoses
host = ''
port = 5555

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((host, port))
values = []
rotation = [0, 0, 0]

SDA = 16
SCL = 0

drive = pca9865.pca9865(SDA, SCL)

def getValue():
    global values, s, rotation, drive, targetPoses
    prevTime = 0
    while 1:
        try:
            message, address = s.recvfrom(8192)
            currentTime = utime.ticks_ms()
            values = str(message).split(',')
            rotation[0] = float(values[14])
            rotation[1] = float(values[15])
            rotation[2] = 0#str(values[16])
            if (rotation[0] >= 90) and (rotation[0] <= 270):
                #drive.setangle(1, int((rotation[0]-180)))
                targetPoses[1] = int((rotation[0]-180))
            if(currentTime - prevTime >= 2000):
                prevTime = currentTime
                print(rotation)
            else:
                pass
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            print(rotation)

_thread.start_new_thread(getValue, ())