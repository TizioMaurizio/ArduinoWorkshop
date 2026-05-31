# nRF24_ServoStream

Streams servo angles (0–180) over an nRF24L01 link:

- `esp_tx.ino` — ESP8266 transmitter (reads serial slider)
- `uno_rx.ino` — Uno receiver that drives the servo
- `servo_gui.py` — Tkinter slider that auto-detects the ESP port

Library: `RF24`.
