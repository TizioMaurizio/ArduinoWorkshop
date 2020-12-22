import pca9865
import utime
import _thread

SDA = 16
SCL = 0

drive = pca9865.pca9865(SDA, SCL)



def sign(n):
    if n > 0:
        return 1
    elif n < 0:
        return -1
    else:
        return 0

#Smoothly move to the destination angle
currentMotor = 1
targetPoses = [0, 90, 60, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
servos = [0, 90, 60, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
INTERVAL = 20 #(milliseconds) lower value speeds up the movement but beware of the real speed of the thread
INCREMENT = 4 #increase this to move faster when interval is at minimum possible
previousMillis = 0

def move():
    global INTERVAL, INCREMENT, servos, targetPoses, drive, previousMillis, count
    while True:
        currentMillis = utime.ticks_ms()
        if (currentMillis - previousMillis >= INTERVAL):
            previousMillis = currentMillis
            for i in range(16):
                if (servos[i] != targetPoses[i]):
                    deltaMove = targetPoses[i] - servos[i]
                    if (abs(deltaMove) <= INCREMENT):
                        servos[i] = targetPoses[i]
                    else:
                        servos[i] += INCREMENT * sign(deltaMove);
                    drive.setangle(i, servos[i])


_thread.start_new_thread(move, ())