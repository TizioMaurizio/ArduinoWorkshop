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
        serial_port.read()
        master = Tk()
        w = Scale(master, from_=0, to=42)
        w.pack()
        current = ' '
        def callbackC(a):
          global current
          if current != 'c':
              current = 'c'
              serial_port.write(b'c')
              serial_port.read()
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
          
        def callbackB(a):
          global current
          if current != 'b':
              current = 'b'
              serial_port.write(b'b')
              serial_port.read()
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
        def callbackD(a):
          global current
          if current != 'd':
              current = 'd'
              serial_port.write(b'd')
              serial_port.read()
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
        def callbackE(a):
          global current
          if current != 'e':
              current = 'e'
              serial_port.write(b'e')
              serial_port.read()
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
        def callbackA(a):
          global current
          if current != 'a':
              current = 'a'
              serial_port.write(b'a')
              serial_port.read()
          else:
              pass
          serial_port.write(bytes(str(a),'utf8'))
          #serial_port.read()
        w = Scale(master, from_=10, to=180, orient=HORIZONTAL, label='MotorA', length=1000, sliderlength = 50, width = 50, command=callbackA)
        w.pack()
        w.set(90);
        w = Scale(master, from_=0, to=180, orient=HORIZONTAL, label='MotorB', length=1000,  sliderlength = 50, width = 50,command=callbackB)
        w.pack()
        w.set(180);
        w = Scale(master, from_=0, to=180, orient=HORIZONTAL, label='MotorC', length=1000,  sliderlength = 50, width = 50,command=callbackC)
        w.pack()
        w.set(160);
        w = Scale(master, from_=90, to=160, orient=HORIZONTAL, label='MotorD', length=500,  sliderlength = 50, width = 50,command=callbackD)
        w.pack()
        w = Scale(master, from_=0, to=180, orient=HORIZONTAL, label='MotorE', length=1000,  sliderlength = 50, width = 50,command=callbackE)
        w.pack()
        w.set(90)
        

        #b = Button(text="click me", command=callback)
        #b.pack()
        
        serial_port.read()
        #serial_port.write(b'180')
        mainloop()







