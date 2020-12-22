import machine
#import servoTest
import ledTest
import servoDrive

def mqtt_callback(topic, msg):
    print((topic, msg))
    if topic == b'led':
        ledTest.setLed(int(msg))
    elif topic == b'servo':
        servoDrive.currentMotor = int(msg)
    elif topic == b'angle':
        servoDrive.targetPoses[servoDrive.currentMotor] = int(msg)
    elif topic == b'rest':
        servoDrive.drive.alloff()
        