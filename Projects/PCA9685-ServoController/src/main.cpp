// PCA9685 Servo Controller
// Target board: Arduino Uno (ATmega328P)
// RAM budget: ~1.5 KB usable
//
// Serial protocol (9600 baud, 8N1):
//   Receive: "<channel>,<angle>\n"   channel=0..15, angle=0..180
//   Reply:   "OK\n" or "ERR:<message>\n"
//
// Input sources (both parsed identically):
//   - USB Serial (Pin 0/1) — for PC testing and debug
//   - SoftwareSerial on Pin 2 (RX) — from ESP32-CAM GPIO 13
//
// PCA9685 I2C address: 0x40 (default), 400 kHz

#include <Arduino.h>
#include <Wire.h>
#include <SoftwareSerial.h>
#include <Adafruit_PWMServoDriver.h>

// --- Configuration -----------------------------------------------------------
constexpr uint8_t  PCA9685_ADDR       = 0x40;
constexpr uint32_t SERIAL_BAUD        = 9600;
constexpr uint32_t ESP_BAUD           = 4800;    // matches ESP32 UART2, low for SoftwareSerial reliability
constexpr uint8_t  ESP_RX_PIN         = 2;       // Arduino pin 2 ← ESP32 GPIO 13
constexpr uint8_t  ESP_TX_PIN         = 3;       // not used (no reply to ESP32)
constexpr uint16_t SERVO_FREQ_HZ      = 50;
constexpr uint16_t SERVO_PULSE_MIN_US = 500;   // 0 degrees
constexpr uint16_t SERVO_PULSE_MAX_US = 2500;  // 180 degrees
constexpr uint8_t  MAX_CHANNELS       = 16;
constexpr uint8_t  MAX_ANGLE          = 180;

// Serial receive buffer (longest valid message: "15,180\n" = 7 chars + null)
constexpr uint8_t  RX_BUF_SIZE        = 16;

// --- Globals -----------------------------------------------------------------
Adafruit_PWMServoDriver pca(PCA9685_ADDR);
SoftwareSerial espSerial(ESP_RX_PIN, ESP_TX_PIN);

static char    rx_buf[RX_BUF_SIZE];
static uint8_t rx_idx = 0;
static char    esp_buf[RX_BUF_SIZE];
static uint8_t esp_idx = 0;
static unsigned long esp_last_byte_ms = 0;

// --- Helpers -----------------------------------------------------------------

// Convert angle (0–180) to PCA9685 pulse-width in microseconds,
// then to a 12-bit tick count at the configured PWM frequency.
static uint16_t angle_to_pulse(uint8_t angle) {
    uint32_t pulse_us = map(angle, 0, MAX_ANGLE, SERVO_PULSE_MIN_US, SERVO_PULSE_MAX_US);
    // PCA9685 has 4096 ticks per period.  Period = 1e6 / SERVO_FREQ_HZ µs.
    // tick = pulse_us * 4096 / period_us
    uint32_t period_us = 1000000UL / SERVO_FREQ_HZ;
    return (uint16_t)((pulse_us * 4096UL) / period_us);
}

static bool parse_and_execute(const char *line) {
    // Expected format: "<channel>,<angle>"
    const char *comma = strchr(line, ',');
    if (!comma) {
        Serial.println(F("ERR:no comma"));
        return false;
    }

    long channel = atol(line);
    long angle   = atol(comma + 1);

    if (channel < 0 || channel >= MAX_CHANNELS) {
        Serial.println(F("ERR:ch 0-15"));
        return false;
    }
    if (angle < 0 || angle > MAX_ANGLE) {
        Serial.println(F("ERR:ang 0-180"));
        return false;
    }

    uint16_t tick = angle_to_pulse((uint8_t)angle);
    pca.setPWM((uint8_t)channel, 0, tick);
    Serial.println(F("OK"));
    return true;
}

// Non-blocking line reader. Works with any stream + buffer pair.
static bool readline(Stream &port, char *buf, uint8_t &idx) {
    while (port.available()) {
        char c = (char)port.read();
        if (c == '\n' || c == '\r') {
            if (idx > 0) {
                buf[idx] = '\0';
                idx = 0;
                return true;
            }
            continue;
        }
        if (idx < RX_BUF_SIZE - 1) {
            buf[idx++] = c;
        } else {
            idx = 0;
            Serial.println(F("ERR:overflow"));
        }
    }
    return false;
}

// --- Setup / Loop ------------------------------------------------------------

void setup() {
    Serial.begin(SERIAL_BAUD);
    espSerial.begin(ESP_BAUD);

    Wire.begin();
    Wire.setClock(400000UL);  // 400 kHz Fast-mode I2C

    pca.begin();
    pca.setOscillatorFrequency(25000000);  // PCA9685 internal osc ~25 MHz
    pca.setPWMFreq(SERVO_FREQ_HZ);

    // Centre all servos on startup (90 degrees)
    uint16_t centre_tick = angle_to_pulse(90);
    for (uint8_t ch = 0; ch < MAX_CHANNELS; ch++) {
        pca.setPWM(ch, 0, centre_tick);
    }

    Serial.println(F("PCA9685 ready"));
    Serial.print(F("ESP RX on pin "));
    Serial.println(ESP_RX_PIN);
}

void loop() {
    // Read from USB Serial (PC testing)
    if (readline(Serial, rx_buf, rx_idx)) {
        parse_and_execute(rx_buf);
    }
    // Read from ESP32 SoftwareSerial (Pin 2)
    if (readline(espSerial, esp_buf, esp_idx)) {
        esp_last_byte_ms = millis();
        Serial.print(F("[ESP] "));
        Serial.println(esp_buf);
        parse_and_execute(esp_buf);
    }
    // Watchdog: if SoftwareSerial goes silent for 2s, re-init to clear
    // any byte-boundary desync
    if (millis() - esp_last_byte_ms > 2000) {
        esp_last_byte_ms = millis();
        esp_idx = 0;
        espSerial.end();
        espSerial.begin(ESP_BAUD);
    }
}
