from Controller import Ev3Mqtt

class DraggableGroup():
    dragged = 0
    prevx = 0
    prevy = 0
    i = 0
    mqtt = False
    topic = 'scan'
    payload = {'name': str(Ev3Mqtt.time.time())}
    def __init__(self, widget):
        self.dragged = widget
        widget.bind("<ButtonPress-1>", self.on_start)
        widget.bind("<B1-Motion>", self.on_drag)
        widget.bind("<ButtonRelease-1>", self.on_drop)
        widget.configure(cursor="hand1")

    def on_start(self, event):
        # you could use this method to create a floating window
        # that represents what is being dragged.
        self.prevx = event.x
        self.prevy = event.y
        if self.mqtt:
            Ev3Mqtt.send(self.pub_topic, self.payload)
        pass

    def on_drag(self, event):
        deltax = event.x - self.prevx
        deltay = event.y - self.prevy
        self.dragged.place(x=self.dragged.winfo_x() + deltax, y=self.dragged.winfo_y() + deltay)

        pass

    def on_drop(self, event):
        self.dragged["text"] = int(self.dragged["text"]) + 1

    def on_message(self, payload):
        print("message received by ", self)
        self.dragged.configure(text="10")
        if self.topic == 'lmao':
            print('writing testFileMqtt.py')
            f = open("testFileMqtt.py","w+")
            f.write(payload['file'])
            f.close()