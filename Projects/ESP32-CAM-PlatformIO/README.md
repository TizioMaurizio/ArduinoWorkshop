# ESP32-CAM Robot Arm Car — VR Teleoperation

Drive an ELEGOO Smart Robot Car with a servo arm and ESP32-CAM, controlled from a Meta Quest 2 in VR. Head tracking moves the arm, right joystick drives the car, and you see what the camera sees.

<p align="center">
  <img src="photo_2026-04-20_02-25-38.jpg" width="45%" />
  <img src="photo_2026-04-20_02-25-39.jpg" width="45%" />
</p>

## Quick Start

1. **Turn on the mobile hotspot**
   - SSID: `Physical Metaverse 2.4GHz2`
   - Password: `earthbound`

2. **Connect your devices to the hotspot**
   - PC (Wi-Fi or Ethernet → hotspot tether)
   - Meta Quest 2 (Wi-Fi settings → connect to hotspot)

3. **Connect Quest 2 to PC**
   - USB-C cable → enable Oculus Link when prompted

4. **Power on the robot**
   - Flip the power switch on the ELEGOO car base
   - The ESP32-CAM (arm) and ESP32-WROVER (car) connect to Wi-Fi automatically
   - Wait ~5 seconds for the blue LED to stop blinking

5. **Open Godot and press Play**
   - Open `Projects/ESP32-CAM-PlatformIO/Godot/project.godot` in Godot 4.6
   - Press **F5** (or the Play button)
   - Put on the headset — you should see the camera feed and the arm follows your head

## Controls

| Input | Action |
|-------|--------|
| Head rotation | Arm yaw + pitch (servo channels 0, 3) |
| Right joystick Y | Drive forward / backward |
| Right joystick X | Turn left / right |
| Keyboard I/J/K/L | Car fallback (fwd/left/back/right) |

## How It Works

```
Quest 2 (VR)  ──USB Link──▶  PC (Godot 4.6 + OpenXR)
                                │
                    Wi-Fi hotspot (phone)
                       │              │
              ┌────────┘              └────────┐
              ▼                                ▼
     ESP32-CAM (arm)                   ESP32-WROVER (car)
     IP auto-discovered                IP auto-discovered
     ├─ UDP :9685  servo cmds          ├─ TCP :100  motor JSON
     ├─ UDP :82    JPEG stream         └─ UDP :9999 discovery
     ├─ HTTP :80   camera settings
     └─ UDP :9999  discovery
              │
         UART 4800 baud
              ▼
        Arduino UNO
        PCA9685 servo driver
```

All IPs are auto-discovered via UDP broadcast on port 9999 — no hardcoded addresses.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No video feed | Check hotspot is on, robot powered, wait 5s for WiFi |
| Arm doesn't move | Power cycle the robot (ESP32-CAM reboots in ~3s) |
| Car doesn't drive | Check right joystick in VR, or use I/J/K/L keys |
| White/frozen first frame | Normal — auto-recovers in 3s (sensor warmup) |
| Wrong IP after hotspot restart | Auto-discovery handles this — just restart Godot |

## Project Structure

```
ESP32-CAM-PlatformIO/
├── src/main.cpp              — ESP32-CAM firmware (servo bridge + UDP stream)
├── Godot/
│   ├── project.godot         — Godot 4.6 XR project
│   ├── camera_stream.gd      — UDP/TCP stream receiver + auto-discovery
│   ├── servo_controller.gd   — Head tracking → servo angles
│   ├── car_controller.gd     — Joystick → car motor commands
│   └── fullscreen_stream.gdshader — Stereo VR overlay
├── docs/BUILD_LOG.md         — Detailed build log
└── README.md                 — This file
```
