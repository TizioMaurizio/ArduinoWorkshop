import cv2
import numpy as np
import serial
import time
from typing import Dict

import mss
from PIL import Image
from screeninfo import get_monitors


def nothing(x):
    pass
 
cv2.namedWindow("Trackbars")
 
cv2.createTrackbar("B", "Trackbars", 0, 255, nothing)
cv2.createTrackbar("G", "Trackbars", 0, 255, nothing)
cv2.createTrackbar("R", "Trackbars", 0, 255, nothing)

cap = cv2.VideoCapture('http://192.168.1.3:8080/video')

while(True):
    ret, frame = cap.read()
    scale_percent = 60 # percent of original size
    width = int(frame.shape[1] * scale_percent / 100)
    height = int(frame.shape[0] * scale_percent / 100)
    dim = (width, height)
    # half size:
    image = cv2.resize(frame, dim, interpolation = cv2.INTER_LINEAR)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    B = cv2.getTrackbarPos("B", "Trackbars")
    G = cv2.getTrackbarPos("G", "Trackbars")
    R = cv2.getTrackbarPos("R", "Trackbars")

    green = np.uint8([[[B, G, R]]])
    hsvGreen = cv2.cvtColor(green,cv2.COLOR_BGR2HSV)
    lowerLimit = np.uint8([hsvGreen[0][0][0]-10,100,100])
    upperLimit = np.uint8([hsvGreen[0][0][0]+10,255,255])

    mask = cv2.inRange(hsv, lowerLimit, upperLimit)

    result = cv2.bitwise_and(image	, image	, mask=mask)

    cv2.imshow("frame", image)
    cv2.imshow("mask", mask)
    cv2.imshow("result", result)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        cv2.destroyAllWindows()
        break

cap.release()
cv2.destroyAllWindows()