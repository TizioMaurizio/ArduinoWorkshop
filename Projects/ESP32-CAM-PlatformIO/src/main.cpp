#include <Arduino.h>
#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ESPmDNS.h>

// WARNING!!! Make sure that you have either selected ESP32 Wrover Module,
//            or another board which has PSRAM enabled

// Select camera model
//#define CAMERA_MODEL_WROVER_KIT
//#define CAMERA_MODEL_ESP_EYE
//#define CAMERA_MODEL_M5STACK_PSRAM
//#define CAMERA_MODEL_M5STACK_WIDE
#define CAMERA_MODEL_AI_THINKER

#include "camera_pins.h"

// --- Wi-Fi credentials -------------------------------------------------------
const char* ssid     = "Physical Metaverse 2.4GHz2";
const char* password = "earthbound";

// --- UDP listener for angle commands from Godot ------------------------------
// Protocol: receives "<channel>,<angle>\n" packets, forwards to Arduino serial.
constexpr uint16_t UDP_PORT = 9685;

// --- UDP discovery broadcast (same protocol as ELEGOO car) -------------------
constexpr uint16_t DISCOVERY_PORT = 9999;
constexpr unsigned long DISCOVERY_INTERVAL_MS = 2000;
WiFiUDP discovery_udp;

// --- Serial2 (UART2): dedicated clean link to Arduino ------------------------
// GPIO 14/15 are JTAG strapping pins — cause flash/boot glitches when loaded.
// GPIO 13 is free on AI-Thinker (not camera, not LED, not strapping). Safe.
constexpr int ARDUINO_TX_PIN  = 13;   // ESP32 → Arduino RX
constexpr int ARDUINO_RX_PIN  = -1;   // not wired — we only send, never receive
constexpr uint32_t ARDUINO_BAUD = 4800;   // low baud for SoftwareSerial reliability
constexpr uint32_t SERIAL_BAUD  = 115200;

WiFiUDP udp;
HardwareSerial ArduinoSerial(2);  // UART2

void startCameraServer();

void setup() {
  Serial.begin(SERIAL_BAUD);
  Serial.setDebugOutput(true);
  Serial.println();

  // NOTE: UART2 init is deferred until after startCameraServer()
  // because the camera/SD driver may reconfigure GPIO 13 (HS2_DATA3).

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  //init with high specs to pre-allocate larger buffers
  if(psramFound()){
    config.frame_size = FRAMESIZE_UXGA;
    config.jpeg_quality = 10;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

#if defined(CAMERA_MODEL_ESP_EYE)
  pinMode(13, INPUT_PULLUP);
  pinMode(14, INPUT_PULLUP);
#endif

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  //initial sensors are flipped vertically and colors are a bit saturated
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);//flip it back
    s->set_brightness(s, 1);//up the blightness just a bit
    s->set_saturation(s, -2);//lower the saturation
  }
  //drop down frame size for higher initial frame rate
  s->set_framesize(s, FRAMESIZE_QVGA);

#if defined(CAMERA_MODEL_M5STACK_WIDE)
  s->set_vflip(s, 1);
  s->set_hmirror(s, 1);
#endif

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("WiFi connected");

  // mDNS: advertise as esp32-8E0A7C.local (based on MAC suffix)
  if (MDNS.begin("esp32-8E0A7C")) {
    MDNS.addService("http", "tcp", 80);
    MDNS.addService("servo-udp", "udp", UDP_PORT);
    Serial.println("[mDNS] esp32-8E0A7C.local");
  } else {
    Serial.println("[mDNS] failed to start");
  }

  // Start UDP listener for Godot angle commands
  udp.begin(UDP_PORT);
  Serial.printf("[Bridge] UDP listening on port %u\n", UDP_PORT);

  // Start UDP discovery broadcaster
  discovery_udp.begin(0);  // ephemeral port for sending
  Serial.printf("[Discovery] Broadcasting on port %u every %lums\n",
                DISCOVERY_PORT, DISCOVERY_INTERVAL_MS);

  startCameraServer();

  // Initialize UART2 AFTER camera server so GPIO 13 pin mux is ours.
  ArduinoSerial.begin(ARDUINO_BAUD, SERIAL_8N1, ARDUINO_RX_PIN, ARDUINO_TX_PIN);
  Serial.printf("[Bridge] UART2 → Arduino on TX=GPIO%d RX=GPIO%d @ %u baud\n",
                ARDUINO_TX_PIN, ARDUINO_RX_PIN, ARDUINO_BAUD);

  Serial.print("Camera Ready! Use 'http://");
  Serial.print(WiFi.localIP());
  Serial.println("' to connect");
}

void loop() {
  // --- Discovery broadcast (every 2s) ----------------------------------------
  static unsigned long last_discovery = 0;
  if (millis() - last_discovery >= DISCOVERY_INTERVAL_MS) {
    last_discovery = millis();
    IPAddress broadcast_ip = WiFi.localIP();
    broadcast_ip[3] = 255;
    char buf[128];
    snprintf(buf, sizeof(buf),
             "{\"service\":\"esp32-cam-arm\",\"ip\":\"%s\",\"port\":%u,\"servo\":%u,\"cam\":81}",
             WiFi.localIP().toString().c_str(), 80, UDP_PORT);
    discovery_udp.beginPacket(broadcast_ip, DISCOVERY_PORT);
    discovery_udp.print(buf);
    discovery_udp.endPacket();
  }

  // --- Forward UDP packets from Godot → Arduino serial -----------------------
  int packet_size = udp.parsePacket();
  if (packet_size > 0) {
    char buf[64];
    int len = udp.read(buf, sizeof(buf) - 1);
    if (len > 0) {
      buf[len] = '\0';
      Serial.printf("[FWD] %s", buf);    // debug echo on USB serial
      ArduinoSerial.print(buf);          // forward "<ch>,<angle>\n" to Arduino
    }
  }

  // Echo Arduino responses (OK/ERR) to USB debug serial
  while (ArduinoSerial.available()) {
    Serial.write(ArduinoSerial.read());
  }
}
