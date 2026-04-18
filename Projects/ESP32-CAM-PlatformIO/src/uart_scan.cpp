/*
 * UART Pin Scanner for ELEGOO Smart Robot Car V4.0 V2 (ESP32-S3-WROOM-1)
 *
 * Scans GPIO pairs to find which ones connect to the Arduino UNO UART.
 * Sends {Factory} on each TX candidate, checks each RX candidate for response.
 *
 * Build: pio run -e elegoo_car -t upload --upload-port COM9
 * Monitor: pio device monitor -e elegoo_car
 *
 * SAFE: only briefly opens each UART, sends one message, then releases pins.
 */

#include <Arduino.h>

// Candidate GPIOs for TX/RX on ESP32-S3-WROOM-1
// Excluded: 0(boot), 19/20(USB), 26-32(flash/PSRAM)
static const int candidate_pins[] = {
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    11, 12, 13, 14, 15, 16, 17, 18, 21,
    33, 34, 35, 36, 37, 38, 39, 40, 41, 42,
    43, 44, 45, 46, 47, 48
};
static const int NUM_PINS = sizeof(candidate_pins) / sizeof(candidate_pins[0]);

static constexpr uint32_t BAUD = 9600;

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000) delay(10);

    Serial.println("\n======================================");
    Serial.println("  UART Pin Scanner — ELEGOO Car V2");
    Serial.println("======================================\n");
    Serial.printf("Testing %d candidate pins at %u baud\n", NUM_PINS, BAUD);
    Serial.println("Sending {Factory} on each TX, listening on each RX...\n");

    // Phase 1: Try each TX pin while listening on all RX pins
    for (int tx_idx = 0; tx_idx < NUM_PINS; tx_idx++) {
        int tx_pin = candidate_pins[tx_idx];

        for (int rx_idx = 0; rx_idx < NUM_PINS; rx_idx++) {
            int rx_pin = candidate_pins[rx_idx];
            if (rx_pin == tx_pin) continue;

            // Open Serial1 with this TX/RX pair
            Serial1.begin(BAUD, SERIAL_8N1, rx_pin, tx_pin);
            delay(5);

            // Flush any garbage
            while (Serial1.available()) Serial1.read();

            // Send factory init command
            Serial1.print("{Factory}");
            Serial1.flush();

            // Wait for response
            delay(150);

            String response = "";
            while (Serial1.available()) {
                char c = Serial1.read();
                if (c >= 0x20 && c <= 0x7E) {  // printable ASCII only
                    response += c;
                }
            }

            Serial1.end();

            if (response.length() > 0) {
                Serial.printf("*** HIT *** TX=GPIO%d  RX=GPIO%d  Response: %s\n",
                              tx_pin, rx_pin, response.c_str());
            }
        }

        // Progress indicator every pin
        if ((tx_idx + 1) % 5 == 0) {
            Serial.printf("[progress] Tested TX GPIO %d (%d/%d)\n",
                          tx_pin, tx_idx + 1, NUM_PINS);
        }
    }

    Serial.println("\n======================================");
    Serial.println("  Scan complete");
    Serial.println("======================================");
    Serial.println("If no HITs found, try with car power cycled.");
    Serial.println("The Arduino UNO must be running stock ELEGOO firmware.");
}

void loop() {
    delay(10000);
}
