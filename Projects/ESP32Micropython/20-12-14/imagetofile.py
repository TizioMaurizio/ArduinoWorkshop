import camera
import os
import utime
import machine
def capture():
    os.chdir('webserver')
    
    f = open('data.jpg', 'w')
    camera.init(1)
    buf = camera.capture()
    f.write(buf)
    f.close()
    f = open('data2.jpg', 'w')
    buf = camera.capture()
    f.write(buf)
    camera.deinit()
    f.close()

def capture3():
    os.chdir('webserver')
    
    f = open('data.jpg', 'w')
    camera.init(1)
    buf = camera.capture()
    f.write(buf)
    f = open('data'+str(1)+'.jpg', 'w')
    buf = camera.capture()
    f.write(buf)
    camera.deinit()
    f.close()

def capture4():
    os.chdir('webserver')
    camera.init(1)
    for i in range(100):
        f = open('frame'+str(i)+'.jpg', 'w')
        buf = camera.capture()
        f.write(buf)
    camera.deinit()
    f.close()


def capture2s():
    os.chdir('webserver')
    camera.init(1)
    begin = utime.ticks_ms()
    time = begin
    prev = time
    i=0
    machine.sleep(500)
    #while(time - begin < 2000):
        #if(time - prev > -1):
    prev = time
    i=i+1
    name = 'frame'+str(i)+'.jpg'
    print(name)
    f = open(name, 'w')
    buf = camera.capture()
    f.write(buf)
    f.close()
        #time = utime.ticks_ms()
    camera.deinit()
