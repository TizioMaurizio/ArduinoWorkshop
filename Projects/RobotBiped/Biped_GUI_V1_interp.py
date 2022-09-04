import tkinter as tk
import threading
import time
import json
import serial
import traceback
#Continously publishes the value of the horizontal slider on topic 'angle'

MODE = 'USB' #SOCKET or USB
INTERVAL = 0.20
STEP = 5
UPDATED = True

RECEIVER = 'esp32new'

prevTime = 0
currentMotor = 1
prevMotor = 1
doReset = False
#jsonPoses = [0, 20, 0, 0, -15, 20, 0, 0, -20, 0, 0, 0, 0, 0, 0, 0]
jsonPoses = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
prevJsonPoses = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
startingPoses = [90, 102, 121, 91, 80, 104, 95, 72, 73, 90]
startingPoses = [90, 90, 90, 90, 90, 90, 90, 90, 90, 90]
poseOffset = [0, 12, 31, 1, -10, 0, 0, 0, 0, 0, 0, 14, 5, -18, -17, 0]
savedPoses = dict()
jointSliders = []
savedButtons = []

try:
    arduino = serial.Serial("COM4", 115200, timeout=0)
except:
    print('Arduino USB not found.')

buttons = []
message = ''
#positions = {}
def send_angles_socket():
    global prevTime, RECEIVER, jsonPoses, servoValue, INTERVAL, STEP, prevValue, master, END, currentMotor ,prevMotor, doReset, jsonPoses, prevJsonPoses, message, positions, buttons
    import socket
    import traceback
    host = ''
    port = 5555
    RECTIME = 20
    RECSIZE = 4096
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    RECEIVER = 'a'#socket.gethostbyname(RECEIVER)
    def savePosition():
        toSave = ['save',entry.get(),jsonPoses]
        payload = json.dumps(toSave, indent=4)
        print(payload)
        s.sendto(payload.encode(), (RECEIVER, 5555))
        getPositions()

    def removePosition():
        toRemove = ['remove',entry.get()]
        payload = json.dumps(toRemove, indent=4)
        print(payload)
        s.sendto(payload.encode(), (RECEIVER, 5555))
        getPositions()

    def getPositions():
        global message, positions, buttons
        for b in buttons:
            b.destroy()
        buttons = []
        askPositions = 'positions'
        payload = json.dumps(askPositions, indent=4)
        print(payload.encode())
        s.sendto(payload.encode(), (RECEIVER, 5555))

        def receive():
            global message
            message = ''
            message2, address = s.recvfrom(RECSIZE)
            message = message2.decode("utf-8", "ignore")

        th = threading.Thread(target=receive)
        th.setDaemon(True)
        th.start()
        startReceive = time.time()
        while message == '':
            try:
                if(time.time()-startReceive > 6):
                    raise Exception("timeout")
                if message != '':
                    print('Received:',message)
                    message=('global positions\n'+message)
                    #positions = {'start': [0, 45, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'mid': [0, 45, 45, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 'end': [0, 30, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}
                    print(exec(message))
                    for key in positions: #from message
                        q = tk.Button(master, text=key, command= lambda: positionButton(positions))
                        q.pack()
                        buttons.append(q)
            except:
                traceback.print_exc()
                print('Couldn\'t download positions')
                break

    q = tk.Button(master, text="Download positions", bg='yellow', command=getPositions)
    q.pack()
    tk.Label(master, text="Position name").pack()
    entry = tk.Entry(master)
    entry.pack()
    q = tk.Button(master, text="Save new position", bg='green', command=savePosition)
    q.pack()
    q = tk.Button(master, text="Remove position", bg='red', command=removePosition)
    q.pack()

    #getPositions()

    def sitStand():
        global jsonPoses
        value = w0.get()
        value0 = value
        toChange = [1, 2, 3]
        for i in toChange:
            value = value0
            if i != 1:
                value = -value
            if i == 1:
                value += 30
            if i == 3:
                value = int(value / 2)
            jsonPoses[i] = value
            jsonPoses[15 - i] = -value

    def leanLeft():
        global jsonPoses
        value = w0.get()
        value0 = value
        toChange = [0]
        for i in toChange:
            #jsonPoses[i] = value
            jsonPoses[9-i] = value

    def allMotors():
        global jointSliders
        for i in range(10):
            if i >= 5:
                j = 15 - (9-i)
            else:
                j = i
            jsonPoses[j] = jointSliders[i].get()


    #jsonPoses = [0, 20, 0, 0, -10, 15, 0, 0, -20, 0, 0, 0, 0, 0, 0, 0]
    startup = True
    while True:
        try:
            if(END):
                print('closing')
                return
            '''if (abs(servoValue - targetPose) > STEP):
                servoValue += sign(targetPose - servoValue) * STEP
            else:
                servoValue = targetPose'''
            servoValue = targetPose
            if(time.time()-prevTime >= INTERVAL):
                #sitStand()
                #leanLeft()
                allMotors()
                #for i in range(16):
                    #jsonPoses[i] = value
                '''
                jsonPoses[1] = w1.get()
                jsonPoses[2] = w2.get()
                jsonPoses[3] = w3.get()
                jsonPoses[4] = w4.get()
                '''

                if(jsonPoses != prevJsonPoses or startup):
                #if True:
                    angleString = "s";
                    for st in jsonPoses:
                        #st = st + 90
                        #st =
                        s2 = str(st)
                        if s2.__len__() < 3:
                            for i in range(3 - s2.__len__()):
                                s2 = '0' + s2
                        angleString = angleString + s2
                    angleString = angleString + '\n'
                    #payload = bytes(angleString, " utf-8")
                    #s.sendto(payload, (RECEIVER, 5555))
                    arduino.write(angleString.encode(encoding='utf-8'))
                    response = ''
                    time.sleep(0.01)
                    response = arduino.readline()
                    print('MESSAGE: ', angleString, 'RESPONSE: ', ('s'+response.decode()))
                    arduino.flushInput()
                    if (angleString == 's'+response.decode()):
                        print('OK')
                        startup = False
                    else:
                        print('ERROR')
                    #print(payload)
                    prevJsonPoses = list(jsonPoses)
                    prevTime = time.time()
                '''elif(doReset):
                    Mqtt.sendInt('reset', 0)
                    doReset = False
                    prevTime = time.time()'''
        except:
            traceback.print_exc()

#string example "s090102121091080000000000000000000104095072073090\n"
#"s090090090090090000000000000000000090090090090090\n"
def getAngleString(jsonAngles):
    angleString = "s";

    for st in jsonAngles:
        # st = st + 90
        # st =
        s2 = str(st)
        if s2.__len__() < 3:
            for i in range(3 - s2.__len__()):
                s2 = '0' + s2
        angleString = angleString + s2
    angleString = angleString + '\n'
    return angleString

def sendUSB(toSend):
    arduino.write(toSend.encode(encoding='utf-8'))
    response = ''
    time.sleep(0.05)
    response = arduino.readline()
    print('MESSAGE: ', toSend, 'RESPONSE: ', ('s' + response.decode()))
    arduino.flushInput()
    if (toSend == 's' + response.decode()):
        print('OK')
        return 0
    else:
        print('ERROR')
        return 1

def allMotors():
    global jointSliders, jsonPoses
    for i in range(10):
        if i >= 5:
            j = 15 - (9-i)
        else:
            j = i
        jsonPoses[j] = jointSliders[i].get() + poseOffset[j]

PAUSE = False
def sendAnglesUSB():
    global prevJsonPoses, jsonPoses
    #getPositions()

    '''def sitStand():
        global jsonPoses
        value0 = value
        toChange = [1, 2, 3]
        for i in toChange:
            value = value0
            if i != 1:
                value = -value
            if i == 1:
                value += 30
            if i == 3:
                value = int(value / 2)
            jsonPoses[i] = value
            jsonPoses[15 - i] = -value'''

    '''def leanLeft():
        global jsonPoses
        value0 = value
        toChange = [0]
        for i in toChange:
            #jsonPoses[i] = value
            jsonPoses[9-i] = value'''

    startup = 1
    prevTime = 0
    while True:
        try:
            servoValue = targetPose
            if(time.time()-prevTime >= INTERVAL):
                #sitStand()
                #leanLeft()
                allMotors()
                if(jsonPoses != prevJsonPoses or startup):
                    if(not PAUSE):
                        angleString = getAngleString(jsonPoses)
                        startup = sendUSB(angleString)
                        #print(payload)
                        prevJsonPoses = list(jsonPoses)
                        prevTime = time.time()
        except:
            traceback.print_exc()



def clicked(event):
    global CLICKED, PAUSE
    CLICKED = event.widget
    print('clicked',CLICKED)
    if CLICKED in jointSliders:
        PAUSE = False

def setPose():
    global PAUSE
    PAUSE = True
    print('set',CLICKED['text'])
    poses = savedPoses[CLICKED['text']]
    print(poses)
    for i in range(10):
        if i<5:
            j = i
        else:
            j = 16-(10-i)
        jointSliders[i].set(poses[j])
    allMotors()
    sendUSB(getAngleString(jsonPoses))

def playback():
    global PAUSE
    PAUSE = True
    print("REPLAY: " + str(savedPoses))
    for n in range(13):
        time.sleep(0.3)
        poses = savedPoses["s"+str(n+1)]
        print(poses)
        for i in range(10):
            if i<5:
                j = i
            else:
                j = 16-(10-i)
            jointSliders[i].set(poses[j])
        allMotors()
        sendUSB(getAngleString(jsonPoses))
    while(True):
        for n in range(10):
            time.sleep(0.3)
            poses = savedPoses["s"+str(n+4)]
            print(poses)
            for i in range(10):
                if i<5:
                    j = i
                else:
                    j = 16-(10-i)
                jointSliders[i].set(poses[j])
            allMotors()
            sendUSB(getAngleString(jsonPoses))
            
def walk():
    global savedPoses
    f = open("narrowGaitV2_interp"+'.json',"r")
    s = f.read()
    import json
    savedPoses = json.loads(s)
    #savedPoses = eval(s)
    print(savedPoses)
    f.close()
    global PAUSE
    PAUSE = True
    print("REPLAY: " + str(savedPoses))
    #for n in range(len(savedPoses)):
    #    time.sleep(0.03)
    #    poses = savedPoses["s"+str(n+1)]
    #    print(poses)
    #    for i in range(10):
    #        if i<5:
    #            j = i
    #        else:
    #            j = 16-(10-i)
    #        jointSliders[i].set(poses[j])
    #    allMotors()
    #    sendUSB(getAngleString(jsonPoses))
    while(True):
        for n in range(len(savedPoses)):
            time.sleep(0.3/(len(savedPoses)*2))
            poses = savedPoses["s"+str(n)]
            print(poses)
            for i in range(10):
                if i<5:
                    j = i
                else:
                    j = 16-(10-i)
                jointSliders[i].set(poses[j])
            allMotors()
            sendUSB(getAngleString(jsonPoses))
    
    

def saveFile():
    text = ENTRY.get()
    f = open(text+'.txt',"w")
    f.write(str(savedPoses))
    f.close()

def loadFile():
    global savedPoses
    text = ENTRY.get()
    f = open(text+'.txt',"r")
    s = f.read()
    savedPoses = eval(s)
    print('savedPoses = ',savedPoses)
    for i in savedPoses:
        newPose = tk.Button(master, text=i, bg='yellow', command=setPose)
        newPose.pack(side = tk.LEFT)
        savedButtons.append(newPose)
    #add playback button
    newPose = tk.Button(master, text="WALK", bg='orange', command=playback)
    newPose.pack(side = tk.LEFT)
    savedButtons.append(newPose)
    f.close()

def savePose():
    global savedPoses
    text = ENTRY.get()
    newPose = tk.Button(master, text=text, bg='yellow', command=setPose)
    if(newPose['text'] not in savedPoses):
        newPose.pack(side = tk.LEFT)
        savedButtons.append(newPose)
    jsonSave = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    for i in range(16):
        jsonSave[i] = jsonPoses[i] - poseOffset[i]
    savedPoses[newPose['text']] = list(jsonSave)
    print('save',newPose['text'])
    print(savedPoses)

def removeSaved(event):
    print("remove", event.widget)
    if event.widget in savedButtons:
        savedPoses.pop(event.widget['text'])
        savedButtons.remove(event.widget)
        event.widget.destroy()

def reset():
    for i in range(10):
        jointSliders[i].set(startingPoses[i])
    allMotors()
    sendUSB(getAngleString(jsonPoses))

def sign(n):
    if n > 0:
        return 1
    elif n < 0:
        return -1
    else:
        return 0

targetPose = 0
servoValue = 0
master = tk.Tk()
#w0 = tk.Scale(master, from_=-90, to=90, orient=tk.HORIZONTAL, activebackground='white', troughcolor='blue', width= 30, length= 500, command=sliderCallback0)
#w0.pack()
for i in range(10):
    if(i>=5):
        color = 'blue'
    else:
        color = 'red'
    jointSliders.append(tk.Scale(master, from_=0, to=180, orient=tk.HORIZONTAL, activebackground='white', troughcolor=color, width= 10, length= 500))
    jointSliders[i].set(startingPoses[i])
    jointSliders[i].pack()

RESET = tk.Button(master, text='RESET', command=reset)
RESET.pack()
tk.Label(master, text="Position name").pack()
ENTRY = tk.Entry(master)
ENTRY.pack()
LOADFILE = tk.Button(master, text="Load file", bg='green', command=loadFile)
LOADFILE.pack()
SAVEFILE = tk.Button(master, text="Save file", bg='green', command=saveFile)
SAVEFILE.pack()
SAVE = tk.Button(master, text="Save pose", bg='green', command=savePose)
SAVE.pack()
WALK = tk.Button(master, text="WALK", bg='purple', command=walk)
WALK.pack()

master.bind("<3>", removeSaved)
master.bind("<1>", clicked)
if(MODE == 'USB'):
    th = threading.Thread(target=sendAnglesUSB)
    th.setDaemon(True)
    th.start()
if(MODE == 'SOCKET'):
    th = threading.Thread(target=send_angles_socket)
    th.setDaemon(True)
    th.start()
tk.mainloop()
