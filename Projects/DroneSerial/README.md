# DroneSerial

Arduino bridge that converts ASCII serial commands into PWM outputs feeding a drone receiver's four channels (throttle, yaw, pitch, roll on D6/D5/D10/D11). Returns to neutral after a 300 ms timeout if no command arrives.

Sketch: `DroneSerial.ino`. Companion: `controller.py` for sending input.
