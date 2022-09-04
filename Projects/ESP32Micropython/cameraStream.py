import socket
import _thread
import utime
import servoDrive
import ujson
import sys
import camera
servoDrive.INTERVAL = 10
host = ''
port = 5555
RECTIME = 20
RECSIZE = 256   #check this if jsons don't work
STOP = 0
RECEIVER = "192.168.1.8"
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((host, port))

def send(toSend):
    s.sendto(toSend.encode(), (RECEIVER, 5555))

camera.init(1)
_thread.start_new_thread(getValue, ())
camera.deinit()
