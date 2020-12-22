import machine
import utime
import servoDrive
import pca9865

SDA = 16
SCL = 0
drive = pca9865.pca9865(SDA, SCL)

p = machine.Pin(13, machine.Pin.OUT)
#p.value(0)
try:
    servoDrive.stop()
    currentMillis = utime.ticks_ms()
    while servoDrive.STOP != 2:
        if(utime.ticks_ms()-currentMillis > 5000):
            print('Couldnt stop servoDrive')
            break
        pass
    drive.alloff()
except:
    pass
machine.reset()