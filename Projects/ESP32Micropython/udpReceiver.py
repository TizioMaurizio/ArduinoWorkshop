import socket
import _thread
import utime
import servoDrive
import ujson
import sys
servoDrive.INTERVAL = 10
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
    global values, s, rotation, positions
    prevTime = 0
    while not STOP:
        try:
            currentTime = utime.ticks_ms()
            if (currentTime - prevTime >= RECTIME):
                prevTime = currentTime
                message, address = s.recvfrom(RECSIZE)
                try:
                    received = message.decode("utf-8", "ignore")  # transform payload into str
                    received = ujson.loads(received)
                    if isinstance(received[0], int):
                        servoDrive.jsonPoses = received
                    else:
                        print(received)
                    if received == 'positions':
                        print('Sending saved positions')
                        f = open("positions_file.py", "r")
                        file_content = f.read()
                        #print("sending",file_content)
                        file_content = file_content.encode()
                        s.sendto(file_content, (RECEIVER, 5555))
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
    servoDrive.stop()
    del sys.modules['udpReceiver']
    print('udpReceiver.getValue() thread will terminate at next udp packet received')

def send(toSend):
    s.sendto(toSend.encode(), (RECEIVER, 5555))

_thread.start_new_thread(getValue, ())
print("Receiver is:", RECEIVER)