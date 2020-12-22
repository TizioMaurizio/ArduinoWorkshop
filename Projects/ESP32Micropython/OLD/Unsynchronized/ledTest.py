
p = machine.Pin(2, machine.Pin.OUT)

def setLed(value):
    global p
    p.value(value)