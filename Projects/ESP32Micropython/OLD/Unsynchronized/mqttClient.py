# Complete project details at https://RandomNerdTutorials.com
import machine
import servoTest
import time
from umqttsimple import MQTTClient
import ubinascii
import micropython
import network
import esp

esp.osdebug(None)
import gc

gc.collect()

from ledTest import setLed

import _thread

stop = 0;
mqtt_server = '192.168.1.5'
# EXAMPLE IP ADDRESS
# mqtt_server = '192.168.1.144'
client_id = ubinascii.hexlify(machine.unique_id())
topic_sub = 'led'
topic_sub2 = 'servo'
topic_pub = 'lmao'

last_message = 0
message_interval = 5
counter = 0


# Complete project details at https://RandomNerdTutorials.com

def sub_cb(topic, msg):
    print((topic, msg))
    if topic == b'led':
        setLed(int(msg))
    elif topic == b'servo':
        servoTest.setServo(int(msg))

def connect_and_subscribe():
    global client_id, mqtt_server, topic_sub
    client = MQTTClient(client_id, mqtt_server)
    client.set_callback(sub_cb)
    client.connect()
    client.subscribe(topic_sub)
    client.subscribe(topic_sub2)
    print('Connected to %s MQTT broker, subscribed to %s topic and %s topic' % (mqtt_server, topic_sub, topic_sub2))
    return client


def restart_and_reconnect():
    print('Failed to connect to MQTT broker. Reconnecting...')
    time.sleep(10)
    machine.reset()

def start_mqtt():
    global counter, last_message, message_interval, stop
    while True:
        try:
            client.check_msg()
            if (time.time() - last_message) > message_interval:
                msg = b'Hello #%d' % counter
                # client.publish(topic_pub, msg)
                last_message = time.time()
                counter += 1
                if stop == 1:
                    print('stopping MQTT client')
                    break
        except OSError as e:
            restart_and_reconnect()

try:
    client = connect_and_subscribe()
except OSError as e:
    restart_and_reconnect()

_thread.start_new_thread(start_mqtt, ())



