def walk():
    import time
    print("start walk")
    time.sleep(2)
    f = open("narrowGaitV2"+'.txt',"r")
    s = f.read()
    Biped_GUI_V1.savedPoses = eval(s)
    f.close()
    Biped_GUI_V1.playback()

import threading
th = threading.Thread(target=walk)
th.setDaemon(True)
th.start()

import Biped_GUI_V1
   

 