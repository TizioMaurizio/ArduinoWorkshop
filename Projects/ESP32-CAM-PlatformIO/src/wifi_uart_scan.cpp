/*
 * WiFi-based UART Pin Scanner for ELEGOO Smart Robot Car V4.0 V2
 * 
 * Reports results over TCP (port 100) instead of Serial, avoiding USB CDC issues.
 * Connect via: python -c "import socket; s=socket.socket(); s.connect(('IP',100)); print(s.recv(8192))"
 *
 * Scans candidate GPIO pairs by sending {Factory} and checking for Arduino response.
 */

#include <Arduino.h>
#include <WiFi.h>

const char* ssid     = "Physical Metaverse 2.4GHz2";
const char* password = "earthbound";

WiFiServer tcp_server(100);

// Safe candidate GPIOs for S3-WROOM-1 (no PSRAM variant)
// Excluded: 0 (strapping), 19/20 (USB D-/D+), 26-32 (not exposed on WROOM-1)
static const int pins[] = {
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    11, 12, 13, 14, 15, 16, 17, 18, 21,
    35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
    45, 46, 47, 48
};
static const int NUM_PINS = sizeof(pins) / sizeof(pins[0]);

void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000) delay(10);

    Serial.println("\n=== WiFi UART Pin Scanner ===");

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
        delay(500);
        Serial.print(".");
    }

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("\nWiFi FAILED");
        return;
    }

    Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
    tcp_server.begin();
    Serial.println("TCP server on port 100 — connect to start scan");
}

void loop() {
    WiFiClient client = tcp_server.available();
    if (!client) return;

    client.println("=== UART Pin Scanner ===");
    client.printf("Scanning %d candidate pins at 9600 baud\n\n", NUM_PINS);
    Serial.println("[SCAN] Client connected, starting scan...");

    int hits = 0;

    for (int tx_idx = 0; tx_idx < NUM_PINS; tx_idx++) {
        int tx_pin = pins[tx_idx];

        for (int rx_idx = 0; rx_idx < NUM_PINS; rx_idx++) {
            int rx_pin = pins[rx_idx];
            if (rx_pin == tx_pin) continue;

            Serial1.begin(9600, SERIAL_8N1, rx_pin, tx_pin);
            delay(5);

            // Flush garbage
            while (Serial1.available()) Serial1.read();

            // Send factory init
            Serial1.print("{Factory}");
            Serial1.flush();
            delay(200);

            String response = "";
            while (Serial1.available()) {
                char c = Serial1.read();
                if (c >= 0x20 && c <= 0x7E) {
                    response += c;
                }
            }

            Serial1.end();

            if (response.length() > 0) {
                hits++;
                String msg = "*** HIT *** TX=GPIO" + String(tx_pin) +
                             " RX=GPIO" + String(rx_pin) +
                             " Response: " + response;
                client.println(msg);
                Serial.println(msg);
            }
        }

        // Progress every 5 TX pins
        if ((tx_idx + 1) % 5 == 0) {
            client.printf("[progress] TX GPIO %d (%d/%d)\n", tx_pin, tx_idx + 1, NUM_PINS);
        }

        // Keep client alive
        if (!client.connected()) {
            Serial.println("[SCAN] Client disconnected, aborting");
            return;
        }
    }

    client.printf("\n=== Scan complete: %d hits ===\n", hits);
    Serial.printf("[SCAN] Complete: %d hits\n", hits);
    client.stop();
}
