# ESP32-CAM

Two ESP32-CAM examples:

- `CameraWebServer.ino` — stock OV2640 web streaming server with control panel.
- `CameraMqttServer.ino` — variant that publishes status / receives commands over MQTT.

Pins live in `camera_pins.h`; the gzipped HTML UI is in `camera_index.h`.
