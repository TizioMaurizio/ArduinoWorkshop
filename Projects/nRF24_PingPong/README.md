# nRF24_PingPong

Round-trip latency tester for nRF24L01 radios:

- `uno_ping.ino` — Arduino Uno transmitter
- `esp_pong.ino` — ESP8266 NodeMCU responder
- `pingpong_gui.py` — Tkinter monitor showing live RTT, even with only one side connected

Library: `RF24`.
