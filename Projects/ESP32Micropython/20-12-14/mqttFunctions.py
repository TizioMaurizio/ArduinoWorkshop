import machine
#import servoTest
import ledTest
import servoDrive
import ujson
import sys

class MyException(Exception):
    pass

def mqtt_callback(topic, msg):
    #print((topic, msg))
    if topic == b'led':
        ledTest.setLed(int(msg))
    elif topic == b'servo':
        servoDrive.currentMotor = int(msg)
    elif topic == b'angle':
        servoDrive.targetPoses[servoDrive.currentMotor] = int(msg)
    elif topic == b'rest':
        servoDrive.drive.alloff()
    elif topic == b'reset':
        servoDrive.resetMotors()
    elif topic == b'json':
        try:
            received = msg.decode("utf-8", "ignore")  # transform payload into str
            received = ujson.loads(received)
            #print(received)
            servoDrive.jsonPoses = received
        except MyException as err:
            print('json receive error')
            sys.print_exception(err)
        '''try:
            print(received[str(1+2)])
        except MyException as err:
            print('json access error')
            sys.print_exception(err)'''

        