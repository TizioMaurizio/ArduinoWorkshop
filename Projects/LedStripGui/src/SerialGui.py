import tkinter as tk
from tkinter import ttk
import serial
import time

# Serial configuration
SERIAL_PORT = "COM7"  # Change this to the correct port name
BAUD_RATE = 9600

#tkinter gui with r g b sliders to send color on serial and receive ack from arduino
class SerialGui:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Serial GUI")
        self.root.geometry("400x200")
        self.root.resizable(False, False)

        self.color = "r0g0b0"

        self.serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)

        self.frame = tk.Frame(self.root)
        self.frame.pack()

        self.r = tk.Scale(self.frame, from_=0, to=70, orient=tk.HORIZONTAL, label="R")
        self.r.pack()

        self.g = tk.Scale(self.frame, from_=0, to=140, orient=tk.HORIZONTAL, label="G")
        self.g.pack()

        self.b = tk.Scale(self.frame, from_=0, to=255, orient=tk.HORIZONTAL, label="B")
        self.b.pack()

        #make sliders longer and colored
        self.r.config(troughcolor="red", length=300)
        self.g.config(troughcolor="green", length=300)
        self.b.config(troughcolor="blue", length=300)

        #show a square with current color
        self.color_square = tk.Label(self.frame, text="Color", width=10, height=5)
        self.color_square.pack()


        self.ack = tk.Label(self.frame, text="Waiting for ACK")
        self.ack.pack()

        self.prev_send_time = 0

        #fire r every 100 ms
        self.root.after(100, self.send_color, None)

        self.root.mainloop()

    def send_color(self, event):
        #send only if 1s have passed since last send
        if time.time() - self.prev_send_time > 0.01:
            color = "r" + str(self.r.get()) + "g" + str(self.g.get()) + "b" + str(self.b.get())
            if self.color != color:
                self.color = color
                print("sending "+self.color)
                self.serial.write(self.color.encode())
                self.serial.write("\n".encode())
            #receive everything
            self.receive_ack()
            self.prev_send_time = time.time()
            #use r.get g.get and b.get to set square color, avoid unknown color name "r0g0b0"
            try:
                self.color_square.config(bg="#%02x%02x%02x" % (self.r.get(), self.g.get(), self.b.get()))
            except:
                pass
            
            

            
        
        self.root.after(100, self.send_color, None)



    def receive_ack(self):
        #serial readstring and print
        ack = self.serial.readline().decode()
        if ack != "":
            print("received "+ack)
            self.ack.config(text=ack)

        

#main
if __name__ == "__main__":
    SerialGui()
    