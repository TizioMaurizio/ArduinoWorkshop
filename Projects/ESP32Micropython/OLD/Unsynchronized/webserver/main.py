# Complete project details at https://RandomNerdTutorials.com
import uos
import machine
import _thread
try:
  import usocket as socket
except:
  import socket

led = -1

def web_page():
  global led
  if led.value() == 1:
    gpio_state="ON"
  else:
    gpio_state="OFF"
  
  html = """<html><head> <title>ESP Web Server</title> <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,"> <style>html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
  h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #e7bd3b; border: none; 
  border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
  .button2{background-color: #4286f4;}</style></head><body> <h1>ESP Web Server</h1> 
  <p>GPIO14 state: <strong>""" + gpio_state + """</strong></p><p><a href="/?led=on"><button class="button">ON</button></a></p>
  <p><a href="/?led=off"><button class="button button2">OFF</button></a></p></body></html>"""
  return html

def start():
    global led
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 80))
    s.listen(5)
    led = machine.Pin(16, machine.Pin.OUT)

    while True:
      conn, addr = s.accept()
      print('Got a connection from %s' % str(addr))
      request = conn.recv(1024)
      request = str(request)
      print('Content = %s' % request)
      led_on = request.find('/?led=on')
      led_off = request.find('/?led=off')
      if led_on == 6:
        print('LED ON')
        led.value(1)
      if led_off == 6:
        print('LED OFF')
        led.value(0)
      response = web_page()
      conn.send('HTTP/1.1 200 OK\n')
      conn.send('Content-Type: text/html\n')
      conn.send('Connection: close\n\n')
      conn.sendall(response)
      conn.close()

print('\nWelcome back! Here are some available functions you may like to use:\n\n<import mqttClient> to start the mqtt client\n<_thread.start_new_thread(start(), ())> to start the htttp webserver\n<drive = pca9865.pca9865(13,15)> to instantiate a Servo Drive object (setangle and alloff useful methods)\n\nIMPORTANT - Pins 2, 14, 15 disable the SD card if used, Pin 4 is onboard flash led\n')
import mqttClient
