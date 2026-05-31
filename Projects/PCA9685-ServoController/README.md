# PCA9685-ServoController

16-channel PCA9685 servo bench:

- `main.cpp` — Arduino sketch listening for `<channel>,<angle>\n` packets
- `serial_bridge.py` — auto-detects the board and forwards GUI commands
- `servo_gui.py` — Tkinter slider grid for all 16 channels @ 115200 baud
