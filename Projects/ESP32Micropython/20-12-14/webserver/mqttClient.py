# Complete project details at https://RandomNerdTutorials.com
# import servoTest
import time
import uos
from umqttsimple import MQTTClient
import ubinascii
import machine
import micropython
import network
import esp

esp.osdebug(None)
import gc

gc.collect()

# from ledTest import setLed

import _thread
import mqttFunctions

stop = 0;
mqtt_server = '192.168.1.5'
# EXAMPLE IP ADDRESS
# mqtt_server = '192.168.1.144'
client_id = ubinascii.hexlify(machine.unique_id())

subscribe_list = ['led', 'servo', 'angle', 'rest']

topic_pub = 'lmao'

last_message = 0
message_interval = 5
counter = 0



# Complete project details at https://RandomNerdTutorials.com

def sub_cb(topic, msg):
    mqttFunctions.mqtt_callback(topic,msg)


def connect_and_subscribe():
    global client_id, mqtt_server, topic_sub
    client = MQTTClient(client_id, mqtt_server)
    client.set_callback(sub_cb)
    client.connect()
    for i in subscribe_list:
        client.subscribe(i)
        print('Connected to %s MQTT broker, subscribed to %s topic\n' % (mqtt_server, i))
    return client


def restart_and_reconnect():
    print('Failed to connect to MQTT broker. Reconnecting...')
    time.sleep(10)
    machine.reset()


def start_mqtt():
    global counter, last_message, message_interval, stop, client
    try:
        client = connect_and_subscribe()
    except OSError as e:
        restart_and_reconnect()
    while True:
        try:
            client.check_msg()
            if (time.time() - last_message) > message_interval:
                counter += 1
                if stop == 1:
                    print('stopping MQTT client')
                    break
        except OSError as e:
            restart_and_reconnect()


# LedTest
def setLed(value):
    global p
    p.value(value)


# ServoTest
def degreeToDuty(value):
    value = (((value / 180) * 110) + 25)
    return int(value)


def setServo(angle):
    global servo
    dutyValue = degreeToDuty(angle)
    servo.duty(int(dutyValue))


_thread.start_new_thread(start_mqtt, ())

