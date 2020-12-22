import network
import time
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
for _ in range(10):
	sta_if.connect('RedmiMau', 'mau12397')
	time.sleep(1)
	if sta_if.isconnected():
	    print('Connected.')
	    break
	time.sleep(11)
else:
    print('Fail')