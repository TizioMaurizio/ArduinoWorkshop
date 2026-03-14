import serial
import keyboard
import time

ser = serial.Serial("COM4",115200)

while True:

    ud = 0
    yaw = 0
    pitch = 0
    roll = 0

    if keyboard.is_pressed('w'):
        ud = 1
    elif keyboard.is_pressed('s'):
        ud = -1

    if keyboard.is_pressed('a'):
        yaw = 1
    elif keyboard.is_pressed('d'):
        yaw = -1

    if keyboard.is_pressed('k'):
        pitch = 1
    elif keyboard.is_pressed('i'):
        pitch = -1

    if keyboard.is_pressed('l'):
        roll = 1
    elif keyboard.is_pressed('j'):
        roll = -1

    packet = f"{ud} {yaw} {pitch} {roll}\n"

    ser.write(packet.encode())

    time.sleep(0.05)  # 20Hz