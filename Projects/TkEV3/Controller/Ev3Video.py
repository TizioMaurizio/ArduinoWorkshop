#root is defined HERE
import PIL
from PIL import Image,ImageTk
import cv2
from Model.DraggableGroup import DraggableGroup
import tkinter as tk
import time
import threading

delta = 0
deltaT = 50
#IP CAMERA
width, height = 800, 600
cap = cv2.VideoCapture(0) #'http://admin:@192.168.0.102/video.cgi?.mjpg' IMPORTANTE METTERE I DUE PUNTI DOPO ADMIN
cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
0
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 0)

_, frame = cap.read()

def eat_frames(): #Da eseguire su un thread a parte, consuma continuamente frames dalla webcam in modo che il buffer sia sempre smaltito
    global frame, root, cap
    while True: #one cycle takes around 0.06s on average
        #sec = time.time()
        _, frame = cap.read()
        try:
            root.state()
        except:
            cap.release()
            break
        #print(time.time()-sec)

root = tk.Tk()
seconds = time.time()
lmain = tk.Label(root, text = "1")
lmain.place(x=-100,y=0)
timeLabel = tk.Label(root, text="Frame Time = "+str(delta)+"\nTarget = "+str(deltaT))
timeLabel.place(x=180, y=60)
def show_frame():
    global seconds, deltaT, lmain, frame
    #for i in range(0,2):
    	#cap.grab()
    #_, frame = cap.read()
    #frame = cv2.flip(frame, 1)
    prev = seconds
    cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
    img = PIL.Image.fromarray(cv2image)
    imgtk = ImageTk.PhotoImage(image=img)
    lmain.imgtk = imgtk #to keep a reference
    lmain.configure(image=imgtk)
    seconds = time.time()
    delta = seconds - prev
    sleeptime = int(max(deltaT-delta*1000, 1))
    lmain.after(sleeptime, show_frame)
    text = "Frame Time = %.2f\nTarget = %.2f" % (sleeptime+delta*1000, deltaT)
    timeLabel.configure(text=text)


#WEBCAM
width, height = 400, 300
webcam = cv2.VideoCapture(1)
webcam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
webcam.set(cv2.CAP_PROP_BUFFERSIZE, 1);
webCamLabel = tk.Label(root, text = "1")
webCamLabel.place(x=400,y=0)
dndVideo2 = DraggableGroup(webCamLabel)
seconds2 = time.time()
eatSeconds2 = time.time()
delta2 = 0
_, frame2 = webcam.read()
def eat_frames2(): #Da eseguire su un thread a parte, consuma continuamente frames dalla webcam in modo che il buffer sia sempre smaltito
    global frame2, root, delta2, wecbam, eatSeconds2, deltaT
    prev = eatSeconds2
    _, frame2 = webcam.read()
    try:
        root.state()
        eatSeconds2 = time.time()
        delta3 = eatSeconds2 - prev
        time.sleep(int(max(deltaT-delta3*1000, 0.01)))
        #time.sleep(int(max(deltaT-delta2*1000, 10)))
        eat_frames2()
    except:
        pass
    #print(time.time()-sec)

def show_frame2():
    global seconds2, delta2, deltaT, frame2, frame
    #for i in range(0,2):
    	#cap.grab()
    #_, frame2 = webcam.read()
    #frame = cv2.flip(frame, 1)
    prev = seconds2
    cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA) #CHANGE TO frame2------------------------
    img = PIL.Image.fromarray(cv2image)
    imgtk2 = ImageTk.PhotoImage(image=img)
    webCamLabel.imgtk = imgtk2 #to keep a reference
    webCamLabel.configure(image=imgtk2)
    seconds2 = time.time()
    delta2 = seconds - prev
    sleeptime = int(max(deltaT-delta2*1000, 1))
    webCamLabel.after(sleeptime, show_frame2)
show_frame2()


#th = threading.Thread(target=eat_frames2)
#th.start()