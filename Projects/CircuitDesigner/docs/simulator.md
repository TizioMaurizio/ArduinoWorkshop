# Code Simulator — How It Works

The Circuit Designer includes a built-in Arduino C++ code simulator that can parse and visually step through Arduino sketches without uploading to hardware. It runs entirely in the browser using JavaScript-based interpretation of C++ syntax patterns.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  CodeSimulator.tsx                    │
│                                                      │
│  ┌──────────────┐    ┌───────────────────────────┐  │
│  │  Code Editor  │    │   Simulation Output Panel  │  │
│  │  (textarea)   │    │                           │  │
│  │               │    │  ┌─────────────────────┐  │  │
│  │  Arduino C++  │    │  │  LED / Servo Widget  │  │  │
│  │  source code  │    │  └─────────────────────┘  │  │
│  │               │    │  ┌─────────────────────┐  │  │
│  │  ┌──────────┐ │    │  │   Serial Monitor    │  │  │
│  │  │ Line     │ │    │  │   (scrolling log)   │  │  │
│  │  │ Highlight│ │    │  └─────────────────────┘  │  │
│  │  │ Overlay  │ │    │  ┌─────────────────────┐  │  │
│  │  └──────────┘ │    │  │   Loop Counter      │  │  │
│  └──────────────┘    │  └─────────────────────┘  │  │
│                       └───────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Execution Pipeline

### 1. Parsing (`parseSketch`)

The source code is split into lines and each line is classified:

| Type      | Detection Rule                            |
|-----------|-------------------------------------------|
| `comment` | Starts with `//`, `/*`, or `*`            |
| `blank`   | Empty after trimming                      |
| `loop`    | Everything else (executable code)         |

### 2. Constant Resolution (`resolveConstants`)

Before execution, the parser scans for constant definitions using the regex:

```
/(?:const\s+\w+\s+|#define\s+)(\w+)\s+(\S+)/g
```

This extracts name→value mappings for:
- `const int LED_PIN = 13;` → `{ LED_PIN: "13" }`
- `#define DELAY_MS 500` → `{ DELAY_MS: "500" }`
- `const unsigned long BLINK_INTERVAL = 1000;` → `{ BLINK_INTERVAL: "1000" }`

These constants are substituted into function arguments during execution.

### 3. Action Extraction (`extractActions`)

Each line is scanned for known Arduino API calls using regex patterns:

| Arduino Function        | Regex Pattern                                      | Simulator Effect                        |
|-------------------------|----------------------------------------------------|-----------------------------------------|
| `digitalWrite(pin, v)`  | `/digitalWrite\(\s*(\w+)\s*,\s*(\w+)\s*\)/`       | Sets `pinStates[pin]` to `true`/`false` |
| `pinMode(pin, mode)`    | `/pinMode\(\s*(\w+)\s*,\s*(\w+)\s*\)/`            | Recognized but no visual effect         |
| `Serial.println("msg")` | `/Serial\.println\(\s*"([^"]*)"\s*\)/`            | Appends text to Serial Monitor          |
| `Serial.begin(baud)`   | `/Serial\.begin\(\s*(\d+)\s*\)/`                   | Recognized (no-op in simulator)         |
| `delay(ms)`            | `/delay\(\s*(\w+)\s*\)/`                            | Pauses stepping for `min(ms, 1500)` ms  |
| `Servo.write(angle)`   | `/\.write\(\s*(\w+)\s*\)/`                          | Sets `servoAngle` state                 |
| `Servo.attach(pin)`    | `/\.attach\(\s*(\w+)\s*\)/`                         | Recognized (marks servo active)         |

### 4. Structure Detection (`start`)

When the user clicks **▶ Run**, the simulator scans the code for `void setup()` and `void loop()` function boundaries by tracking braces:

```
Code:                         Detected regions:
                              
const int LED_PIN = 13;       ← (globals, skipped)
                              
void setup() {                ← setupStart
  pinMode(LED_PIN, OUTPUT);   │ executed once
  Serial.begin(9600);         │
}                             ← setup ends
                              
void loop() {                 ← loopStart
  digitalWrite(LED_PIN, HIGH);│ repeats
  delay(1000);                │ up to 20
  digitalWrite(LED_PIN, LOW); │ iterations
  delay(1000);                │
}                             ← loopEnd
```

### 5. Execution Loop

1. **Setup phase**: Lines from `setupStart` to `loopStart` are stepped through at 100ms per line
2. **Loop phase**: Lines from `loopStart` to `loopEnd` repeat, then jump back to `loopStart`
3. **Delay handling**: `delay(ms)` pauses the next step by `min(ms, 1500)` milliseconds
4. **Termination**: Automatically stops after 20 loop iterations, or when the user clicks **■ Stop**

### 6. State Model

```typescript
interface SimState {
  running: boolean;                    // is the simulator active?
  currentLine: number;                 // index of the highlighted line
  pinStates: Record<string, boolean>;  // digital pin HIGH/LOW states
  servoAngle: number;                  // current servo angle (0-180)
  serialOutput: string[];              // serial monitor log (last 20 lines)
  loopCount: number;                   // loop iteration counter
}
```

## Visual Outputs

### LED Indicator
- Appears when the code contains `LED_PIN` or `digitalWrite`
- Glows red with a shadow effect when the pin is `HIGH`
- Shows dark/off when `LOW`

### Servo Gauge
- Appears when the code contains `Servo` or `.write()`
- Renders a semicircular gauge (0°–180°) with a rotating needle
- Displays the current angle numerically
- Needle animates smoothly via CSS transitions

### Serial Monitor
- Displays `Serial.println()` output in a scrolling terminal-style panel
- Keeps the last 20 lines
- Green monospace text on dark background

### Line Highlighting
- A yellow bar overlays the code editor showing the currently executing line
- Positioned absolutely over the textarea using matching `line-height` (18px)

## Supported Arduino API Surface

| Category    | Supported                                         | Not Supported                     |
|-------------|---------------------------------------------------|-----------------------------------|
| Digital I/O | `pinMode`, `digitalWrite`                         | `digitalRead`                     |
| Analog I/O  | —                                                 | `analogRead`, `analogWrite`       |
| Serial      | `Serial.begin`, `Serial.println`                  | `Serial.print`, `Serial.read`     |
| Timing      | `delay`                                           | `millis`, `micros`, `delayMicroseconds` |
| Servo       | `Servo.attach`, `Servo.write`                     | `Servo.read`, `Servo.writeMicroseconds` |
| Control     | `setup()` / `loop()` structure                    | `if`, `for`, `while`, variables   |

## Limitations

- **No control flow**: `if`, `for`, `while`, `switch` are ignored — every line executes sequentially
- **No variable tracking**: Only `const` / `#define` constants are resolved; runtime variables are not tracked
- **No expressions**: `analogWrite(pin, value * 2)` won't evaluate the expression
- **String-only Serial**: Only `Serial.println("literal string")` is captured; variable printing is not supported
- **Fixed loop count**: Always stops after 20 loop iterations
- **Delay cap**: `delay()` values are capped at 1500ms for usability

## File Format

Circuit files (`.circuit.json`) can include a `code` field:

```json
{
  "name": "Blinking LED",
  "nodes": [...],
  "edges": [...],
  "code": "const int LED_PIN = 13;\n\nvoid setup() {\n  ...\n}\n\nvoid loop() {\n  ...\n}\n",
  "exportedAt": "2026-05-11T00:00:00.000Z"
}
```

When imported, the code is loaded into the editor and the simulator becomes available.
