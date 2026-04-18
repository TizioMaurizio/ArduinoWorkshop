/*
 * ELEGOO Smart Robot Car V4.0 — ESP32-WROVER firmware (STA mode)
 *
 * Original: creates WiFi AP "ELEGOO-XXXX", TCP server on port 100.
 * Modified: connects to existing WiFi network as STA, same TCP bridge.
 *
 * Build with PlatformIO environment [env:elegoo_car].
 *
 * Features:
 *   - WiFi STA with auto-reconnect
 *   - TCP server on port 100 (same JSON protocol as original ELEGOO app)
 *   - Camera HTTP server on ports 80 (control) / 81 (MJPEG stream)
 *   - mDNS: elegoo-car.local
 *   - UDP discovery broadcast on port 9999 (JSON with IP/port)
 *   - Serial2 bridge to Arduino UNO (GPIO 3 RX / GPIO 40 TX, 9600 baud)
 *   - Status LED on GPIO 13
 *
 * Wire protocol (TCP port 100) — unchanged from original:
 *   Client → Car:  {"N":3,"D1":<dir>,"D2":<spd>,"H":"<seq>"}  (move)
 *                   {"N":100,"H":"<seq>"}                       (stop)
 *   Heartbeat:      {Heartbeat}  bidirectional, every ~1s
 *   Car → Client:   JSON responses from Arduino UNO
 *
 * Discovery (UDP port 9999) — new:
 *   Broadcast every 2s: {"service":"elegoo-car","ip":"x.x.x.x","port":100,"cam":81}
 */

#include <Arduino.h>
// Camera disabled: ESP32-S3-WROOM-1 V2 board has unknown camera pin mapping.
// Using wrong pins crashes esp_camera_init(). Re-enable once ELEGOO V2 pinout is confirmed.
// #include "esp_camera.h"
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ESPmDNS.h>

// Camera model for the ELEGOO car — DISABLED pending V2 pin map
// #define CAMERA_MODEL_M5STACK_WIDE
// #include "camera_pins.h"

// --- WiFi credentials --------------------------------------------------------
const char* ssid     = "Physical Metaverse 2.4GHz2";
const char* password = "earthbound";

// --- Serial2 to Arduino UNO --------------------------------------------------
// Discovered via WiFi UART pin scanner (wifi_uart_scan.cpp):
//   TX=GPIO40, RX=GPIO3 — confirmed by Arduino response "error:deserializeJson"
// Original WROVER used GPIO 33 RX / GPIO 4 TX (not available on S3-WROOM-1).
#define RXD2 3
#define TXD2 40
static constexpr uint32_t ARDUINO_BAUD = 9600;

// --- TCP server (same port as original ELEGOO firmware) ----------------------
static constexpr uint16_t TCP_PORT = 100;
WiFiServer tcp_server(TCP_PORT);

// --- UDP discovery broadcast -------------------------------------------------
static constexpr uint16_t DISCOVERY_PORT = 9999;
WiFiUDP discovery_udp;

// --- Status LED (active LOW on ELEGOO board) ---------------------------------
static constexpr int LED_PIN = 13;

// --- Timing constants --------------------------------------------------------
static constexpr unsigned long HEARTBEAT_INTERVAL_MS    = 1000;
static constexpr uint8_t      HEARTBEAT_TIMEOUT_COUNT   = 3;
static constexpr unsigned long DISCOVERY_INTERVAL_MS    = 2000;
static constexpr unsigned long WIFI_RECONNECT_INTERVAL_MS = 5000;
static constexpr unsigned long WIFI_CONNECT_TIMEOUT_MS  = 15000;

// Camera and HTTP server disabled — ESP32-S3-WROOM-1 V2 has unknown camera GPIO map.
// Re-enable init_camera() and startCameraServer() once the correct pin mapping is confirmed.
// Forward declaration kept commented for future use:
// void startCameraServer();

// =============================================================================
// WiFi STA connection
// =============================================================================
static void connect_wifi() {
    WiFi.setTxPower(WIFI_POWER_19_5dBm);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    Serial.printf("[WiFi] Connecting to \"%s\"", ssid);

    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED &&
           millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
        delay(500);
        Serial.print(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WiFi] Connected — IP: %s  RSSI: %d dBm\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI());
    } else {
        Serial.println("\n[WiFi] Connection FAILED — will retry in loop");
    }
}

// =============================================================================
// mDNS advertisement
// =============================================================================
static void start_mdns() {
    if (MDNS.begin("elegoo-car")) {
        MDNS.addService("http", "tcp", 80);
        MDNS.addService("elegoo-car", "tcp", TCP_PORT);
        Serial.println("[mDNS] elegoo-car.local");
    } else {
        Serial.println("[mDNS] failed to start");
    }
}

// =============================================================================
// UDP discovery broadcast
// =============================================================================
static void send_discovery_broadcast() {
    if (WiFi.status() != WL_CONNECTED) return;

    // Subnet broadcast (e.g. 192.168.1.255)
    IPAddress broadcast_ip = WiFi.localIP();
    broadcast_ip[3] = 255;

    char buf[128];
    snprintf(buf, sizeof(buf),
             "{\"service\":\"elegoo-car\",\"ip\":\"%s\",\"port\":%u,\"cam\":81}",
             WiFi.localIP().toString().c_str(), TCP_PORT);

    discovery_udp.beginPacket(broadcast_ip, DISCOVERY_PORT);
    discovery_udp.print(buf);
    discovery_udp.endPacket();
}

// =============================================================================
// TCP bridge — same protocol as original ELEGOO firmware
// Blocking: runs in loop() until client disconnects or heartbeat times out.
// Camera HTTP server continues on its own FreeRTOS tasks.
// =============================================================================
static void handle_tcp_client(WiFiClient& client) {
    Serial.println("[TCP] Client connected");
    digitalWrite(LED_PIN, LOW);  // LED solid = client active

    String read_buf;
    String send_buf;
    uint8_t heartbeat_fail_count = 0;
    bool heartbeat_ack = false;
    bool data_begin = true;
    unsigned long heartbeat_time = millis();

    while (client.connected()) {
        // --- Read from TCP client, forward to Arduino UNO ---
        while (client.available()) {
            char c = client.read();
            if (data_begin && c == '{') {
                data_begin = false;
            }
            if (!data_begin && c != ' ') {
                read_buf += c;
            }
            if (!data_begin && c == '}') {
                data_begin = true;
                if (read_buf.equals("{Heartbeat}")) {
                    heartbeat_ack = true;
                } else {
                    Serial2.print(read_buf);
                }
                read_buf = "";
            }
        }

        // --- Read from Arduino UNO, forward to TCP client ---
        while (Serial2.available()) {
            char c = Serial2.read();
            send_buf += c;
            if (c == '}') {
                client.print(send_buf);
                send_buf = "";
            }
        }

        // --- Heartbeat (every 1s) ---
        if (millis() - heartbeat_time >= HEARTBEAT_INTERVAL_MS) {
            heartbeat_time = millis();
            client.print("{Heartbeat}");

            if (heartbeat_ack) {
                heartbeat_ack = false;
                heartbeat_fail_count = 0;
            } else {
                heartbeat_fail_count++;
            }

            if (heartbeat_fail_count > HEARTBEAT_TIMEOUT_COUNT) {
                Serial.println("[TCP] Heartbeat timeout — disconnecting");
                break;
            }
        }

        // --- Check WiFi still up ---
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[TCP] WiFi lost — disconnecting client");
            break;
        }

        yield();  // Feed watchdog, let FreeRTOS tasks run
    }

    // Client gone — emergency stop
    Serial2.print("{\"N\":100}");
    client.stop();
    Serial.println("[TCP] Client disconnected — car stopped");
}

// =============================================================================
// Factory test passthrough (for Arduino UNO self-test, same as original)
// =============================================================================
static void handle_factory_test() {
    static String factory_buf;

    while (Serial2.available()) {
        char c = Serial2.read();
        factory_buf += c;
        if (c == '}') {
            if (factory_buf.equals("{BT_detection}")) {
                Serial2.print("{BT_OK}");
            } else if (factory_buf.equals("{WA_detection}")) {
                Serial2.print("{");
                // Report WiFi name based on MAC (original behavior)
                uint64_t chipid = ESP.getEfuseMac();
                char mac_str[20];
                sprintf(mac_str, "%04X%08X",
                        (uint16_t)(chipid >> 32), (uint32_t)chipid);
                Serial2.print(mac_str);
                Serial2.print("}");
            }
            factory_buf = "";
        }
    }
}

// =============================================================================
// setup
// =============================================================================
void setup() {
    Serial.begin(115200);

    // ESP32-S3 native USB CDC needs time to enumerate after reset.
    // Wait up to 3 seconds for the host to connect.
    unsigned long usb_wait = millis();
    while (!Serial && millis() - usb_wait < 3000) {
        delay(10);
    }

    Serial2.begin(ARDUINO_BAUD, SERIAL_8N1, RXD2, TXD2);

    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, HIGH);  // LED off at startup

    Serial.println("\n=== ELEGOO Car ESP32-S3-WROOM-1 V2 (STA mode) ===\n");

    // Camera disabled — unknown V2 pin mapping, wrong pins crash esp_camera_init().
    // Motor control via TCP bridge works without camera.
    Serial.println("[CAM] DISABLED — V2 camera pin map unknown");

    // WiFi STA
    connect_wifi();

    if (WiFi.status() == WL_CONNECTED) {
        start_mdns();
        // startCameraServer();  // Re-enable with correct V2 pin map
        tcp_server.begin();
        discovery_udp.begin(0);  // Bind to ephemeral port for sending

        Serial.printf("[TCP]    Listening on port %u\n", TCP_PORT);
        Serial.println("[CAM]    Camera HTTP server disabled");

        digitalWrite(LED_PIN, LOW);  // LED on = connected
    }

    // Signal to Arduino UNO that ESP32 is ready
    Serial2.print("{Factory}");
}

// =============================================================================
// loop
// =============================================================================
void loop() {
    // --- WiFi reconnection ---
    static unsigned long wifi_retry_time = 0;
    if (WiFi.status() != WL_CONNECTED) {
        // Fast LED blink = WiFi disconnected
        digitalWrite(LED_PIN, (millis() / 200) & 1 ? HIGH : LOW);

        if (millis() - wifi_retry_time >= WIFI_RECONNECT_INTERVAL_MS) {
            wifi_retry_time = millis();
            Serial.println("[WiFi] Reconnecting...");
            WiFi.reconnect();
        }
        return;  // Skip TCP/discovery while WiFi is down
    }

    // LED solid on = WiFi connected
    static bool services_started = false;
    if (!services_started) {
        // Services may need restart after reconnection
        tcp_server.begin();
        services_started = true;
        Serial.printf("[WiFi] Reconnected — IP: %s\n",
                      WiFi.localIP().toString().c_str());
        digitalWrite(LED_PIN, LOW);
    }

    // --- UDP discovery broadcast ---
    static unsigned long discovery_time = 0;
    if (millis() - discovery_time >= DISCOVERY_INTERVAL_MS) {
        discovery_time = millis();
        send_discovery_broadcast();
    }

    // --- Accept TCP client (one at a time, same as original) ---
    WiFiClient client = tcp_server.available();
    if (client) {
        services_started = false;  // Re-check after client disconnects
        handle_tcp_client(client);
    } else {
        handle_factory_test();
    }
}
