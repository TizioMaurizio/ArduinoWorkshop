import cv2
import numpy as np
import serial
import time
from typing import Dict

import mss
from PIL import Image

try:
    arduino = serial.Serial('COM5', 9600, timeout=0)
except Exception:
    arduino = None

dictionary: Dict[int, str] = {
    0:"red",
    1:"blue",
    2:"green",
    3:"yellow",
    4:"cyan",
    5:"pink",
    6:"white",
    7:"black",
}
i = 0
width = 1920
height = 1080
s_width = 1920
s_height = 1080
scalingFactor = 0.1

interval = 50 #milliseconds
prevTime = int(round(time.time() * 1000))
cap = cv2.VideoCapture(0)    
frame: np.ndarray
with mss.mss() as sct:
    while(True):
        # The screen part to capture
        monitor = {"top": 0, "left": 0, "width": s_width, "height": s_height}
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "RGBX")
        frame = np.array(img)
        # ret, frame = cap.read()
        
        frameOriginal = frame
        width = int(s_width * scalingFactor)
        height = int(s_height * scalingFactor)
        frame = cv2.resize(frame,(width,height))
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Red color
        imagered = np.zeros((height, width, 3), np.uint8)
        imagered[:] = (0, 0, 255)
        low_red = np.array([0, 80, 80])
        high_red = np.array([10, 255, 255])
        red_mask = cv2.inRange(hsv_frame, low_red, high_red)
        red = cv2.bitwise_and(imagered, imagered, mask=red_mask)
        
        # Blue color
        imageblue = np.zeros((height, width, 3), np.uint8)
        imageblue[:] = (255, 0, 0)
        low_blue = np.array([100, 80, 80])
        high_blue = np.array([110, 255, 255])
        blue_mask = cv2.inRange(hsv_frame, low_blue, high_blue)
        blue = cv2.bitwise_and(imageblue, imageblue, mask=blue_mask)

        # Green color
        imagegreen = np.zeros((height, width, 3), np.uint8)
        imagegreen[:] = (0, 255, 0)
        low_green = np.array([40, 80, 80])
        high_green = np.array([60, 255, 255])
        green_mask = cv2.inRange(hsv_frame, low_green, high_green)
        green = cv2.bitwise_and(imagegreen, imagegreen, mask=green_mask)

        # Yellow color
        imageyellow = np.zeros((height, width, 3), np.uint8)
        imageyellow[:] = (0, 255, 255)
        low_yellow = np.array([10, 80, 80]) #hue 20
        high_yellow = np.array([40, 255, 255])
        yellow_mask = cv2.inRange(hsv_frame, low_yellow, high_yellow)
        yellow = cv2.bitwise_and(imageyellow, imageyellow, mask=yellow_mask)

        # Cyan color
        imagecyan = np.zeros((height, width, 3), np.uint8)
        imagecyan[:] = (255, 255, 0)
        low_cyan = np.array([60, 80, 80])
        high_cyan = np.array([100, 255, 255])
        cyan_mask = cv2.inRange(hsv_frame, low_cyan, high_cyan)
        cyan = cv2.bitwise_and(imagecyan, imagecyan, mask=cyan_mask)

        # Pink color
        imagepink = np.zeros((height, width, 3), np.uint8)
        imagepink[:] = (255, 0, 255)
        low_pink = np.array([110, 80, 80])
        high_pink = np.array([255, 255, 255]) #hue 160
        pink_mask = cv2.inRange(hsv_frame, low_pink, high_pink)
        pink = cv2.bitwise_and(imagepink, imagepink, mask=pink_mask)

        # White color
        imagewhite = np.zeros((height, width, 3), np.uint8)
        imagewhite[:] = (255, 255, 255)
        low_white = np.array([0, 0, 80])
        high_white = np.array([255, 80, 255])
        white_mask = cv2.inRange(hsv_frame, low_white, high_white)
        white = cv2.bitwise_and(imagewhite, imagewhite, mask=white_mask)

        imagesum = cv2.add(red, blue)
        imagesum = cv2.add(imagesum, green)
        imagesum = cv2.add(imagesum, yellow)
        imagesum = cv2.add(imagesum, cyan)
        imagesum = cv2.add(imagesum, pink)
        imagesum = cv2.add(imagesum, white)

        #0 red, 1 blue, 2 green, 3 yellow, 4 cyan, 5 pink, 6 white, 7 off   (+1)
        # Work out what we are looking for
        # Find all pixels where the 3 RGB values match "sought", and count
        results = []
        sought = [0,0,255]
        results.append(np.count_nonzero(np.all(imagesum==sought,axis=2)))
        sought = [255,0,0]
        results.append(np.count_nonzero(np.all(imagesum==sought,axis=2)))
        sought = [0,255,0]
        results.append(np.count_nonzero(np.all(imagesum==sought,axis=2)))
        sought = [0,255,255]
        results.append(np.count_nonzero(np.all(imagesum==sought,axis=2)))
        sought = [255,255,0]
        results.append(np.count_nonzero(np.all(imagesum==sought,axis=2)))
        sought = [255,0,255]
        results.append(np.count_nonzero(np.all(imagesum==sought,axis=2)))
        sought = [255,255,255]  
        results.append(np.count_nonzero(np.all(imagesum==sought,axis=2))*0.2)
        sought = [0,0,0]  
        results.append(np.count_nonzero(np.all(imagesum==sought,axis=2))*0.05)
        currentTime = int(round(time.time() * 1000))
        if(currentTime - prevTime > interval):
            blast = results.index(max(results))
            if(blast != 7):
                arduino.write(chr(blast+48).encode())
                cname: str = dictionary.get(blast, "invalid")
                print(f"[Frame {i}] Firing {cname}")
            prevTime = currentTime
        cv2.imshow("frame", frame)
        cv2.imshow("imagesum", imagesum)
        i += 1
        if(cv2.waitKey(1) & 0xFF == ord('q')):
            break

if arduino:
    print(arduino.name)
    arduino.close()

cap.release()
