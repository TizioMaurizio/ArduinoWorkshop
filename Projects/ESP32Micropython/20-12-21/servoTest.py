import machine

p12 = machine.Pin(12)
servo = machine.PWM(p12,freq=50)

def degreeToDuty(value):
    value = (((value/180)*110) + 25)
    return int(value)

def setServo(angle):
    global servo
    dutyValue = degreeToDuty(angle)
    servo.duty(int(dutyValue))
    
