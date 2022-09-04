import socket
import _thread
import utime
import servoDriveCamera
import ujson
import sys
import camera

servoDriveCamera.INTERVAL = 10
host = ''
port = 5555
RECTIME = 20
RECSIZE = 256   #check this if jsons don't work
STOP = 0
RECEIVER = socket.getaddrinfo('DESKTOP-UEIIPLJ', 80)[0][-1][0]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind((host, port))


def getValue():
    global values, s, rotation, positions, RECEIVER
    prevTime = 0
    servoDriveCamera.SOCK = s
    servoDriveCamera.RECEIVER = RECEIVER
    while not STOP:
        try:
            currentTime = utime.ticks_ms()
            if (currentTime - prevTime >= RECTIME):
                prevTime = currentTime
                message, address = s.recvfrom(RECSIZE)
                try:
                    received = message.decode("utf-8", "ignore")  # transform payload into str
                    #print(received)
                    received = ujson.loads(received)
                    if isinstance(received[0], int):
                        servoDriveCamera.jsonPoses = received
                    else:
                        pass
                        #print(received)
                    if received == 'positions':
                        print('Sending saved positions')
                        f = open("positions_file.py", "r")
                        s.sendto(f.read().encode(), (RECEIVER, 5555))
                        f.close()
                    if received[0] == 'save':
                        f = open("positions_file.py", "r")
                        exec('global positions\n'+f.read())
                        f.close()
                        positions[received[1]] = received[2]
                        f = open("positions_file.py", "w")
                        f.write('positions = '+str(positions))
                        f.close()
                    if received[0] == 'remove':
                        f = open("positions_file.py", "r")
                        exec('global positions\n' + f.read())
                        f.close()
                        positions.pop(received[1], None)
                        f = open("positions_file.py", "w")
                        f.write('positions = ' + str(positions))
                        f.close()

                except Exception as err:
                    print('json receive error')
                    sys.print_exception(err)
        except:
            currentTime = utime.ticks_ms()
            if (currentTime - prevTime >= 2000):
                prevTime = currentTime
                print('error')#, rotation)

    print('Terminating sensorReceiver.getValue()')
    #del sys.modules['sensorReceiver']

def deimport():
    global STOP
    STOP = 1
    servoDriveCamera.stop()
    del sys.modules['udpReceiver']
    print('udpReceiver.getValue() thread will terminate at next udp packet received')

def send(toSend):
    s.sendto(toSend.encode(), (RECEIVER, 5555))



def stream():
    begin = utime.ticks_ms()
    time = utime.ticks_ms()
    prev = time
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
    while True:
        time = utime.ticks_ms()
        if (time-prev>=100):
            s.sendto(camera.capture(), (RECEIVER, 5555))
            prev = utime.ticks_ms()


_thread.start_new_thread(getValue, ())
#_thread.start_new_thread(stream, ())