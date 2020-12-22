import network
import time
def connect(ssid, password):
    ap = network.WLAN(network.AP_IF)
    print('Disabling access point')
    ap.active(False)
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect(ssid, password)
        i = 0
        while not sta_if.isconnected():
            i= i+1
            print('connecting... ', i)
            time.sleep(1)
            if(i == 10):
                sta_if.active(False)
                print('Switching to AP mode')
                ap = network.WLAN(network.AP_IF)
                ap.active(True)
                ap.active(False)
                ap.config(essid='ESP32OLD', authmode=network.AUTH_WPA_WPA2_PSK, password='barbonzi')
                print(ap.config('essid'))
                time.sleep(1)
                print('Activating access point')
                ap.active(True)
                return
        print('Connection successful')
        print(sta_if.ifconfig())

