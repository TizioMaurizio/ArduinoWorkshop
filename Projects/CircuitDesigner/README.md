# Circuit Designer

A React-based visual circuit designer inspired by [circuito.io](https://www.circuito.io/). Design, build, and test Arduino/ESP32 circuits in the browser.

## Features

- **Component Library** — 22 components across 8 categories (microcontrollers, sensors, actuators, passive, power, displays, communication, input)
- **Drag & Drop Canvas** — Drag components from the palette or drop them onto the canvas with React Flow
- **Pin-Level Wiring** — Connect specific pins between components with animated wire visualization
- **Wire & Component Coloring** — Color-code wires (9 colors) and component headers (12 colors) for readability
- **Circuit Validation** — Check for disconnected components, missing ground connections, and voltage mismatches
- **Properties Panel** — View pin definitions, set component values (resistance, capacitance, LED color)
- **Arduino Code Simulator** — Paste or write Arduino C++ sketches and step through them visually in the browser
- **LED Visualization** — See digital pin states toggle an on-screen LED indicator in real time
- **Servo Gauge** — Servo.write() calls animate a semicircular gauge (0°–180°) with a rotating needle
- **Serial Monitor** — Serial.println() output appears in a scrolling terminal panel
- **Export/Import** — Save circuits as JSON files (including code) and reload them later
- **Example Circuits** — Includes Blink LED and Servo Sweep examples with matching Arduino sketches
- **Dark Theme** — Professional dark UI optimized for circuit design

## Components Included

| Category | Components |
|----------|-----------|
| Microcontrollers | Arduino Uno, ESP32 DevKit |
| Sensors | DHT11, HC-SR04, MPU6050, Photoresistor |
| Actuators | Servo SG90, DC Motor, Buzzer |
| Passive | LED, RGB LED, Resistor, Capacitor, Breadboard |
| Displays | OLED 128x64, LCD 16x2 |
| Input | Push Button, Potentiometer, Joystick |
| Power | Breadboard PSU, 9V Battery |
| Communication | nRF24L01, HC-05 Bluetooth |

## Getting Started

```bash
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## Usage

1. **Add components**: Click items in the left palette or drag them onto the canvas
2. **Connect pins**: Drag from one pin handle to another to create wires
3. **Configure**: Select a component to see its properties in the right panel
4. **Validate**: Click "Run Check" in the bottom panel to validate wiring
5. **Export**: Save your circuit design as a JSON file

## Example Circuits

Two ready-made examples are included in `examples/`:

- **Blink LED** (`blink-led.circuit.json`) — Arduino Uno + 220Ω Resistor + LED. The simulator toggles the LED and logs to the serial monitor.
- **Servo Sweep** (`servo-sweep.circuit.json`) — Arduino Uno + SG90 Servo. The simulator sweeps the servo gauge through 0°→45°→90°→135°→180°→90° with serial output.

Import them via the **Import** button in the toolbar.

## Code Simulator

The built-in simulator parses Arduino C++ sketches and visually steps through them without hardware. It supports `digitalWrite`, `Servo.write`, `Serial.println`, `delay`, and `const`/`#define` resolution. See [docs/simulator.md](docs/simulator.md) for the full technical reference.

## Tech Stack

- React 19 + TypeScript
- Vite for build tooling
- React Flow (@xyflow/react) for the node-based canvas
- Zustand for state management

## Development

```bash
npm run dev      # Start dev server with HMR
npm run build    # Production build
npm run preview  # Preview production build
```
