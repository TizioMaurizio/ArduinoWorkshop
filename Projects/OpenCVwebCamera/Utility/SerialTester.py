import serial
import time
arduino = serial.Serial("COM5", 9600, timeout=0)
time.sleep(5)
for i in range(10000):
    arduino.write(chr(0+48).encode())
    arduino.write(chr(1+48).encode())
    arduino.write(chr(2+48).encode())
    arduino.write(chr(3+48).encode())
    arduino.write(chr(4+48).encode())
    arduino.write(chr(5+48).encode())
    arduino.write(chr(6+48).encode())
time.sleep(5)