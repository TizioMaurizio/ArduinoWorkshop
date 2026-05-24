# Robot Biped

A 10-DOF bipedal walking robot controlled via a Python Tkinter GUI over USB serial, using an Arduino Uno and a PCA9685 16-channel PWM servo driver.

## Architecture Overview

```
┌─────────────┐   USB Serial   ┌─────────────┐   I2C (A4/A5)   ┌──────────────┐
│  Python GUI  │ ──────────────→│ Arduino Uno  │ ───────────────→│  PCA9685 PWM │
│ (Tkinter)    │   115200 baud  │              │                 │  Servo Driver│
└─────────────┘                └─────────────┘                 └──────┬───────┘
                                                                       │ 16 PWM channels
                                                         ┌────────────┼────────────┐
                                                    Left Leg (ch 0-4)    Right Leg (ch 11-15)
                                                    5 servos              5 servos
```

## Hardware

| Component | Description |
|-----------|-------------|
| Arduino Uno | Main controller (ATmega328P) |
| PCA9685 | 16-channel I2C PWM servo driver, 60 Hz |
| 10× Servo (SG90 or similar) | 5 per leg — ankle X, ankle Y, knee, hip Y, hip Z |
| External 5V PSU | Servos require a dedicated power supply (not USB power) |

### Servo Channel Mapping

| Channel | Joint | Side | Startup Angle | Calibration Offset |
|---------|-------|------|---------------|--------------------|
| 0 | Ankle X (roll) | Left | 90° | 0° |
| 1 | Ankle Y (pitch) | Left | 102° | +12° |
| 2 | Knee | Left | 121° | +31° |
| 3 | Hip Y (pitch) | Left | 91° | +1° |
| 4 | Hip Z (yaw) | Left | 80° | −10° |
| 5–10 | *Unused* | — | 90° | 0° |
| 11 | Hip Z (yaw) | Right | 104° | +14° |
| 12 | Hip Y (pitch) | Right | 95° | +5° |
| 13 | Knee | Right | 72° | −18° |
| 14 | Ankle Y (pitch) | Right | 73° | −17° |
| 15 | Ankle X (roll) | Right | 90° | 0° |

### Kinematic Chain

```
              Pelvis (fixed)
             /              \
        Hip Z (ch 4)     Hip Z (ch 11)
           |                  |
        Hip Y (ch 3)     Hip Y (ch 12)
           |                  |
        Knee (ch 2)      Knee (ch 13)
           |                  |
      Ankle Y (ch 1)   Ankle Y (ch 14)
           |                  |
      Ankle X (ch 0)   Ankle X (ch 15)
           |                  |
        Left Foot         Right Foot
```

### Wiring

| Signal | Arduino Pin | Destination | Notes |
|--------|-------------|-------------|-------|
| SDA | A4 | PCA9685 SDA | I2C data |
| SCL | A5 | PCA9685 SCL | I2C clock |
| SoftSerial RX | D10 | (optional BT/ESP) | Unused in USB mode |
| SoftSerial TX | D11 | (optional BT/ESP) | Unused in USB mode |
| USB | USB port | PC (COM3) | 115200 baud |

PCA9685 power:
- **VCC** → Arduino 5V (logic only)
- **V+** → External 5–6V PSU (servo power, 2A+ recommended)
- **GND** → Common ground between Arduino, PSU, and PCA9685

## Software

### Arduino Firmware (`RobotArmControllerV2/`)

The firmware listens for serial messages and smoothly ramps servos to target positions.

**Serial Protocol:**
```
Frame: s[16 × 3-digit angles]\n
Example: s090102121091080000000000000000000104095072073090\n
Total length: 50 characters (1 prefix + 48 angle digits + 1 newline)
```

**Servo Movement:**
- Servos ramp at 2° per 30 ms interval (~67°/s) for smooth motion
- Target positions are applied incrementally each loop cycle
- The firmware echoes the received angle string back for verification

**Variants:**
| Folder | Description |
|--------|-------------|
| `RobotArmControllerV2/` | Standard firmware |
| `RobotArmControllerLimits/` | Adds upper/lower angle limits per channel |
| `*_jumpFix/` | Fixes abrupt position jumps on startup |

### Python GUI (`Biped_GUI_V1.py`)

A Tkinter application with 10 horizontal sliders (one per active joint) and gait playback.

**Controls:**
- **10 Sliders** (0–180°): Red = left leg, Blue = right leg
- **RESET**: Return all joints to starting positions
- **Load file / Save file**: Import/export gait sequences as `.txt`
- **Save pose**: Snapshot current slider positions as a named pose
- **WALK**: Load `narrowGaitV2.txt` and loop the walking gait

**Communication:**
- Background thread sends servo angles every 200 ms
- Only sends when angles have changed (delta detection)
- Waits for Arduino echo to confirm delivery

**Variants:**
| File | Description |
|------|-------------|
| `Biped_GUI_V1.py` | Main GUI (USB, COM3) |
| `Biped_GUI_V1_interp.py` | Interpolated gait playback (COM4) |
| `Biped_GUANTO.py` | Glove-sensor input variant |
| `GloveFit.py` | Glove calibration tool |

### Gait Files

Gait data is stored as Python dictionaries mapping pose names to 16-element angle arrays.

| File | Frames | Purpose |
|------|--------|---------|
| `narrowGaitV2.txt` | 13 | Primary walking gait (keyframes) |
| `narrowGaitV2_interp.json` | 110 | Smooth interpolated version |
| `heavyGait.txt` | 13 | Heavy/robust walking pattern |
| `narrowGait.txt` | 18 | Legacy narrow gait |

**Playback sequence:**
1. Frames `s1` → `s13` play once (initialization)
2. Frames `s4` → `s13` loop continuously (steady walking)
3. 300 ms delay between frames → ~3 s per walking cycle

### Visualization (`PlotGait.py`)

Plots joint angles over time using Matplotlib. Left-leg joints are solid lines, right-leg joints are dashed. Color-coded by joint type (ankle=red/green, knee=blue, hip=orange).

## Getting Started

### 1. Upload Firmware

Open `RobotArmControllerV2/RobotArmControllerV2.ino` in Arduino IDE.

**Required libraries:**
- `Adafruit PWM Servo Driver Library`
- `Wire` (built-in)
- `Servo` (built-in)
- `SoftwareSerial` (built-in)

Upload to Arduino Uno.

### 2. Wire the Hardware

1. Connect PCA9685 SDA/SCL to Arduino A4/A5
2. Connect PCA9685 VCC to Arduino 5V, GND to common ground
3. Connect external 5V PSU to PCA9685 V+ screw terminal
4. Connect servos to PCA9685 channels per the mapping table above

### 3. Run the GUI

```bash
pip install pyserial
python Biped_GUI_V1.py
```

Ensure the Arduino is on **COM3** (or edit the port in the script).

### 4. Walk

1. Click **Load file** and type `narrowGaitV2` in the entry box
2. Click **WALK** to start the walking gait loop
3. Right-click a saved pose button to remove it
4. Use **Save file** to export your custom gait sequences

## Circuit Schematic

A Circuit Designer schematic is available at [`examples/robot-biped.circuit.json`](examples/robot-biped.circuit.json). Import it in the [Circuit Designer](../CircuitDesigner/) to view the wiring layout.

> **Note:** The PCA9685 servo driver is not in the Circuit Designer component library. The schematic shows the logical Arduino-to-servo connections. In the physical build, all servo signal wires go through the PCA9685, not directly to Arduino pins.

## Project Structure

```
RobotBiped/
├── Biped_GUI_V1.py                  # Main control GUI
├── Biped_GUI_V1_interp.py           # Interpolated gait GUI
├── Biped_GUANTO.py                  # Glove-input GUI variant
├── GloveFit.py                      # Glove calibration
├── PlotGait.py                      # Gait visualization
├── PlotGaitInterp.py                # Interpolated gait plot
├── walk.py                          # Standalone walk launcher
├── narrowGaitV2.txt                 # Primary walking gait (13 frames)
├── narrowGaitV2_interp.json         # Interpolated gait (110 frames)
├── heavyGait.txt                    # Heavy walking pattern
├── RobotArmControllerV2/            # Arduino firmware
│   └── RobotArmControllerV2.ino
├── RobotArmControllerLimits/        # Firmware with angle limits
│   └── RobotArmControllerV2.ino
├── examples/
│   └── robot-biped.circuit.json     # Circuit Designer schematic
└── old_gaits/                       # Deprecated gait files
```
