# When this script is run for the first time, it might prompt you for 
# permission. Accept the permission and run this script again, then it should 
# send the data as expected.

# Kivy is needed for pyjnius behind the scene.

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.clock import mainthread
from kivy.utils import platform
import threading
import sys
from usb4a import usb
from usbserial4a import serial4a
from pprint import pprint
import time
from tkinter import *

usb_device_list = usb.get_usb_device_list()
usb_device_name_list = [device.getDeviceName() for device in usb_device_list]
usb_device_dict = {
    device.getDeviceName():[            # Device name
        device.getVendorId(),           # Vendor ID
        device.getManufacturerName(),   # Manufacturer name
        device.getProductId(),          # Product ID
        device.getProductName()         # Product name
        ] for device in usb_device_list
    }
pprint(usb_device_dict)

kv = '''
BoxLayout:
    id: box_root
    orientation: 'vertical'
    
    Label:
        size_hint_y: None
        height: '50dp'
        text: 'usbserial4a example'
    
    ScreenManager:
        id: sm
        on_parent: app.uiDict['sm'] = self
        
        Screen:
            name: 'screen_scan'
            BoxLayout:
                orientation: 'vertical'
                ScrollView:
                    BoxLayout:
                        id: box_list
                        orientation: 'vertical'
                        on_parent: app.uiDict['box_list'] = self
                        size_hint_y: None
                        height: max(self.minimum_height, self.parent.height)
                Button:
                    id: btn_scan
                    on_parent: app.uiDict['btn_scan'] = self
                    size_hint_y: None
                    height: '50dp'
                    text: 'Scan USB Device'
                    on_release: app.on_btn_scan_release()
    
        Screen:
            name: 'screen_test'
            BoxLayout:
                orientation: 'vertical'
                ScrollView:
                    size_hint_y: None
                    height: '50dp'
                    TextInput:
                        id: txtInput_write
                        on_parent: app.uiDict['txtInput_write'] = self
                        size_hint_y: None
                        height: max(self.minimum_height, self.parent.height)
                        text: ''
                Button:
                    id: btn_write
                    on_parent: app.uiDict['btn_write'] = self
                    size_hint_y: None
                    height: '50dp'
                    text: 'Write'
                    on_release: app.on_btn_write_release()
                ScrollView:
                    TextInput:
                        id: txtInput_read
                        on_parent: app.uiDict['txtInput_read'] = self
                        size_hint_y: None
                        height: max(self.minimum_height, self.parent.height)
                        readonly: True
                        text: ''
'''

def __init__(self, *args, **kwargs):
        self.uiDict = {}
        self.device_name_list = []
        self.serial_port = None
        self.read_thread = None
        self.port_thread_lock = threading.Lock()
        super(MainApp, self).__init__(*args, **kwargs)

def build(self):
        return Builder.load_string(kv)

def on_stop(self):
        if self.serial_port:
            with self.port_thread_lock:
                self.serial_port.close()
        
def on_btn_scan_release(self):
        self.uiDict['box_list'].clear_widgets()
        self.device_name_list = []
        
        if platform == 'android':
            usb_device_list = usb.get_usb_device_list()
            self.device_name_list = [
                device.getDeviceName() for device in usb_device_list
            ]
        else:
            usb_device_list = list_ports.comports()
            self.device_name_list = [port.device for port in usb_device_list]
        
        for device_name in self.device_name_list:
            btnText = device_name
            button = Button(text=btnText, size_hint_y=None, height='100dp')
            button.bind(on_release=self.on_btn_device_release)
            self.uiDict['box_list'].add_widget(button)
        
def on_btn_device_release(self, btn):
        device_name = btn.text
        
        if platform == 'android':
            device = usb.get_usb_device(device_name)
            if not device:
                raise SerialException(
                    "Device {} not present!".format(device_name)
                )

            if not usb.has_usb_permission(device):
                usb.request_usb_permission(device)
                return
            self.serial_port = serial4a.get_serial_port(
                device_name,
                9600,
                8,
                'N',
                1,
                timeout=1
            )
        else:
            self.serial_port = Serial(
                device_name,
                9600,
                8,
                'N',
                1,
                timeout=1
            )
        
        if self.serial_port.is_open and not self.read_thread:
            self.read_thread = threading.Thread(target = self.read_msg_thread)
            self.read_thread.start()
        
        self.uiDict['sm'].current = 'screen_test'

def on_btn_write_release(self):
        if self.serial_port and self.serial_port.is_open:
            if sys.version_info < (3, 0):
                data = bytes(self.uiDict['txtInput_write'].text + '\n')
            else:
                data = bytes(
                    (self.uiDict['txtInput_write'].text + '\n'),
                    'utf8'
                )
            self.serial_port.write(data)
            self.uiDict['txtInput_read'].text += '[Sent]{}\n'.format(
                self.uiDict['txtInput_write'].text
            )
            self.uiDict['txtInput_write'].text = ''
            
def read_msg_thread(self):
        while True:
            try:
                with self.port_thread_lock:
                    if not self.serial_port.is_open:
                        break
                    received_msg = self.serial_port.read(
                        self.serial_port.in_waiting
                    )
                if received_msg:
                    msg = bytes(received_msg).decode('utf8')
                    self.display_received_msg(msg)
            except Exception as ex:
                raise ex
                
@mainthread
def display_received_msg(self, msg):
        self.uiDict['txtInput_read'].text += msg

if usb_device_list:
    serial_port = serial4a.get_serial_port(
        usb_device_list[0].getDeviceName(), 
        9600,   # Baudrate
        8,      # Number of data bits(5, 6, 7 or 8)
        'N',    # Parity('N', 'E', 'O', 'M' or 'S')
        1)      # Number of stop bits(1, 1.5 or9 2)
    if serial_port and serial_port.is_open:
        received_msg = serial_port.read(
                        serial_port.in_waiting
                    )
        if received_msg:
                    msg = bytes(received_msg).decode('utf8')
        display_received_msg(msg)
        master = Tk()
        w = Scale(master, from_=0, to=42)
        w.pack()
        current = ' '
        def callbackC(a):
          global current
          if current != 'c':
              current = 'c'
              serial_port.write(b'c')
              time.sleep(0.05)
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
          
        def callbackB(a):
          global current
          if current != 'b':
              current = 'b'
              serial_port.write(b'b')
              time.sleep(0.05)
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
        def callbackD(a):
          global current
          if current != 'd':
              current = 'd'
              serial_port.write(b'd')
              time.sleep(0.05)
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
        def callbackE(a):
          global current
          if current != 'e':
              current = 'e'
              serial_port.write(b'e')
              time.sleep(0.05)
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
        def callbackA(a):
          global current
          if current != 'a':
              current = 'a'
              serial_port.write(b'a')
              time.sleep(0.05)
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
        def speedCallback(a):
          global current
          if current != 's':
              current = 's'
              serial_port.write(b's')
              time.sleep(0.05)
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
        reset = 1
        def textCallback():
            global b
            phrase=b''
            for x in range(100):
             next=serial_port.read()
             phrase=phrase+next
             if next==b'\n':
               break
            b.configure(text=phrase)
        def sendBCallback():
            current='b'
            serial_port.write(b'c')
            serial_port.write(b'\0')
            #time.sleep(1)
            serial_port.write(b'b')
        val=120
        def send120Callback():
            global val
            val = val+5
            callbackA(90)
            time.sleep(0.05)
            callbackB(180)
            time.sleep(0.05)
            callbackC(150)
            time.sleep(0.05)
            callbackD(90)
            time.sleep(0.05)
            callbackE(90)
            time.sleep(0.05)
            speedCallback(4)
            time.sleep(0.05)
            #serial_port.write(bytes(str(val),'utf8'))
        def resetCallback():

       #   global reset
          
        #  if reset == 1:
            # callbackA(90)
        #  if reset == 2:
         #    callbackB(180)
          
        #  reset = reset + 1
         # if reset > 2:
          #    reset = 1
         # else:
          #callbackC(160)
          #  callbackD(90)
           # callbackE(90)
            #speedCallback(4):
          callbackA(90)
          time.sleep(0.05)
          callbackB(180)
          time.sleep(0.05)
          callbackC(150)
          time.sleep(0.05)
          callbackD(90)
          time.sleep(0.05)
          callbackE(90)
          time.sleep(0.05)
          #speedCallback(4)
          #time.sleep(0.05)
          w1.set(90)
          w2.set(180)
          w3.set(160)
          w4.set(90)
          w5.set(90)
          #w6.set(4)
          #serial_port.read()
        w1 = Scale(master, from_=50, to=180, orient=HORIZONTAL, label='Hand close/open', length=1000, sliderlength = 100, width = 100, command=callbackA)
        w1.pack()
        w1.set(90);
        w2 = Scale(master, from_=0, to=180, orient=HORIZONTAL, label='Wrist', length=1000,  sliderlength = 100, width = 100,command=callbackB)
        w2.pack()
        w2.set(180);
        w3 = Scale(master, from_=0, to=180, orient=HORIZONTAL, label='Elbow', length=1000,  sliderlength = 100, width = 100,command=callbackC)
        w3.pack()
        w3.set(160);
        w4 = Scale(master, from_=90, to=160, orient=HORIZONTAL, label='Shoulder', length=1000,  sliderlength = 100, width = 100,command=callbackD)
        w4.pack()
        w5 = Scale(master, from_=0, to=180, orient=HORIZONTAL, label='Rotate', length=1000,  sliderlength = 100, width = 100,command=callbackE)
        w5.pack()
        w5.set(90)
        w6 = Scale(master, from_=1, to=16, orient=HORIZONTAL, label='Speed', length=800,  sliderlength = 100, width = 100,command=speedCallback)
        w6.pack()
        w6.set(4)
    
        b = Button(text="RESET", height=2, width=5, command=resetCallback)
        b.pack()
       # b = Button(text="usb monitor", height=2, width=20, command=textCallback)
       # b.pack()
        #c = Button(text="b", height=2, width=20, command=sendBCallback)
        #c.pack()
        #c = Button(text="120", height=2, width=20, command=send120Callback)
        #c.pack()
 
        #serial_port.write(b'180')
        mainloop()















