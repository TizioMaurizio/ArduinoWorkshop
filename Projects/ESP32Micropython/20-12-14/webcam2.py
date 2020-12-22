import camera
from machine import UART
import machine
led = machine.Pin(4, machine.Pin.OUT)
machine.sleep(5000)
led.on()
uart = UART(1, 9600)                         # init with given baudrate
uart.init(9600, bits=8, parity=None, stop=1) # init with given parameters
camera.init()
buf = camera.capture()
camera.deinit()
led.off()