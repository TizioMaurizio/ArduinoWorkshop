import machine

p = machine.Pin(13, machine.Pin.OUT)

def setLed(value):
    global p
    p.value(value)