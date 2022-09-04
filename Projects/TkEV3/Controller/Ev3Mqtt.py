import paho.mqtt.client as mqtt
import json
import time

client = 0
topics = ['asd','lmao']

def init(broker):
    global brokerIP, listeners, client, topics

    brokerIP = broker
    listeners = list(['topic', list()])  # list of arrays consisting of [topic name, list of listeners for this topic]

    mqttTime = time.time()

    # initialize mqtt connection
    try:
        client = mqtt.Client('websockets')
        client.on_subscribe = on_subscribe
        client.on_publish = on_publish
        client.on_message = on_message
        client.on_connect = on_connect
    except:
        client = mqtt.Client()
        client.on_subscribe = on_subscribe
        client.on_publish = on_publish
        client.on_message = on_message
        client.on_connect = on_connect

    client.connect(brokerIP)  # Broker on PC (IP fixed: 192.168.0.2)

    time.sleep(0.1)  # Waiting for the connection to be set
    print('Initializing MQTT')
    client.loop_start()

def on_connect(client, userdata, flags, rc):
    print('Successfully connected to '+brokerIP+'!')
    for topic in topics:
        client.subscribe(topic, 2)
# The callback for SUBSCRIBE.
def on_subscribe(client, userdata, mid, granted_qos):
    print('Successfully subscribed!')
# The callback for when a PUBLISH message is sent to the broker.
def on_publish(client, userdata, mid):
    global mqttTime
    print("Message has been published.")
    #mqttTime = time.time() - mqttStart
    print("MQTT Delay: " + str(mqttTime))
    print()

def on_message(client, userdata, msg):
    print('Message received on ' + msg.topic)
    payload = msg.payload.decode("utf-8", "ignore")  # transform payload into str
    payload = json.loads(payload)
    print(payload)
    notify(msg.topic, payload)

def notify(topic, payload):
    global listeners
    for topics in listeners:
        try:
            if topics[0] == topic:
                for listener in topics[1]:
                    listener.on_message(payload)
        except:
            pass
def subscribe(object): #TODO UNSUBSCRIBE
    global listeners
    for i in listeners: #look for the subscribe topic in 'listeners'
        try:
            if i[0] == object.topic:
                i[1].append(object) #if found add this object to the listeners of that topic (i[1])
                return #end here if the topic was found
        except:
            print('no listeners, creating the first one')
    listeners.append([object.topic, [object]]) #if not found append a new array with [topic, [new listener]]
    print("subscribed ", object," to new topic ", object.topic)
    print(listeners)

def send(topic, payload):
    payload = json.dumps(payload, indent=4)
    client.publish(topic, payload, 0)

def sendInt(topic, value):
    client.publish(topic, value, 2)

