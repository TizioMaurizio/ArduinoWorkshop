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

// --- UDP JPEG stream (port 82) — FreeRTOS task on core 0 --------------------
// Protocol: client sends "STREAM_UDP" to register, resends as keepalive.
//           Server sends fragmented JPEG: 8-byte header + ≤1400B payload.
//           Header: [frame_id:u16LE][frag_idx:u8][frag_count:u8][frame_len:u32LE]
constexpr uint16_t  UDP_STREAM_PORT    = 82;
constexpr uint16_t  UDP_FRAG_SIZE      = 1400;
constexpr uint32_t  UDP_KEEPALIVE_MS   = 5000;  // client timeout
constexpr uint32_t  UDP_STREAM_STACK   = 4096;
constexpr UBaseType_t UDP_STREAM_PRIO  = 1;

// Separate sockets: rx on core 1 (loop), tx on core 0 (stream task)
// Avoids thread-unsafe shared WiFiUDP.
WiFiUDP udp_stream_rx;  // receives commands (main loop, core 1)
WiFiUDP udp_stream_tx;  // sends fragments  (stream task, core 0)

static volatile bool     stream_active  = false;
static volatile uint32_t stream_client_ip   = 0;
static volatile uint16_t stream_client_port = 0;
static volatile uint32_t stream_last_keepalive = 0;
static uint16_t          stream_frame_id = 0;

void startCameraServer();

// --- UDP stream task (runs on core 0) ----------------------------------------
// Captures JPEG from camera, fragments it, sends via udp_stream_tx.
// Separate socket from udp_stream_rx avoids WiFiUDP thread-safety issues.
static void udp_stream_task(void* /*param*/) {
  Serial.println("[UDPStream] Task started on core " + String(xPortGetCoreID()));

  while (true) {
    if (!stream_active) {
      vTaskDelay(pdMS_TO_TICKS(50));
      continue;
    }

    // Check keepalive timeout
    if (millis() - stream_last_keepalive > UDP_KEEPALIVE_MS) {
      stream_active = false;
      Serial.println("[UDPStream] Client timeout — stopping");
      continue;
    }

    // Capture frame
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) {
      vTaskDelay(pdMS_TO_TICKS(10));
      continue;
    }

    // Skip stale frames (fb_count=2: if frame is old, return and grab fresh)
    int64_t age_ms = (esp_timer_get_time() - fb->timestamp.tv_sec * 1000000LL
                      - fb->timestamp.tv_usec) / 1000;
    if (age_ms > 200) {
      esp_camera_fb_return(fb);
      fb = esp_camera_fb_get();
      if (!fb) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
    }

    uint16_t fid = stream_frame_id++;
    size_t frame_len = fb->len;
    size_t frag_count_raw = (frame_len + UDP_FRAG_SIZE - 1) / UDP_FRAG_SIZE;

    // Header uses u8 for frag_count — max 255 fragments = 357 KB.
    // Skip oversized frames (e.g. UXGA at high quality) rather than
    // silently truncating due to uint8_t overflow.
    if (frag_count_raw > 255) {
      Serial.printf("[UDPStream] Frame too large: %u bytes (%u frags) — skipped\n",
                    frame_len, frag_count_raw);
      esp_camera_fb_return(fb);
      vTaskDelay(pdMS_TO_TICKS(83));
      continue;
    }
    uint8_t frag_count = (uint8_t)frag_count_raw;

    IPAddress client_ip(stream_client_ip);
    uint16_t  client_port = stream_client_port;

    for (uint8_t fi = 0; fi < frag_count; fi++) {
      size_t offset = (size_t)fi * UDP_FRAG_SIZE;
      size_t payload_len = frame_len - offset;
      if (payload_len > UDP_FRAG_SIZE) payload_len = UDP_FRAG_SIZE;

      // 8-byte header: frame_id(u16LE) + frag_idx(u8) + frag_count(u8) + frame_len(u32LE)
      uint8_t hdr[8];
      hdr[0] = fid & 0xFF;
      hdr[1] = (fid >> 8) & 0xFF;
      hdr[2] = fi;
      hdr[3] = frag_count;
      hdr[4] = frame_len & 0xFF;
      hdr[5] = (frame_len >> 8) & 0xFF;
      hdr[6] = (frame_len >> 16) & 0xFF;
      hdr[7] = (frame_len >> 24) & 0xFF;

      udp_stream_tx.beginPacket(client_ip, client_port);
      udp_stream_tx.write(hdr, 8);
      udp_stream_tx.write(fb->buf + offset, payload_len);
      udp_stream_tx.endPacket();

      // Yield between fragments to prevent WiFi TX starvation
      if (fi < frag_count - 1) {
        vTaskDelay(1);
      }
    }

    esp_camera_fb_return(fb);

    // Target ~12 FPS: 83ms per frame
    vTaskDelay(pdMS_TO_TICKS(83));
  }
}

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
  // QVGA = 320x240, quality 20 = ~5-10 KB/frame ≈ 150-300 KB/s at 30fps.
  // Can be changed at runtime via HTTP: /control?var=framesize&val=N
  if(psramFound()){
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 20;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_QVGA;
    config.jpeg_quality = 20;
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
  // QVGA (320x240) — good balance of quality and bandwidth.
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
    MDNS.addService("cam-udp", "udp", UDP_STREAM_PORT);
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

  // Start UDP stream sockets
  udp_stream_rx.begin(UDP_STREAM_PORT);  // command reception (core 1 / loop)
  udp_stream_tx.begin(0);                // fragment sending (core 0 / task)
  Serial.printf("[UDPStream] Listening on port %u\n", UDP_STREAM_PORT);

  // Launch stream task pinned to core 0 (loop runs on core 1)
  xTaskCreatePinnedToCore(udp_stream_task, "udp_stream", UDP_STREAM_STACK,
                          nullptr, UDP_STREAM_PRIO, nullptr, 0);

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
             "{\"service\":\"esp32-cam-arm\",\"ip\":\"%s\",\"port\":%u,\"servo\":%u,\"cam\":81,\"udp_cam\":%u}",
             WiFi.localIP().toString().c_str(), 80, UDP_PORT, UDP_STREAM_PORT);
    discovery_udp.beginPacket(broadcast_ip, DISCOVERY_PORT);
    discovery_udp.print(buf);
    discovery_udp.endPacket();
  }

  // --- UDP stream commands (port 82, core 1 rx) ------------------------------
  int stream_pkt = udp_stream_rx.parsePacket();
  if (stream_pkt > 0) {
    char cmd[32];
    int cmd_len = udp_stream_rx.read(cmd, sizeof(cmd) - 1);
    if (cmd_len > 0) {
      cmd[cmd_len] = '\0';
      if (strcmp(cmd, "STREAM_UDP") == 0) {
        stream_client_ip   = (uint32_t)udp_stream_rx.remoteIP();
        stream_client_port = udp_stream_rx.remotePort();
        stream_last_keepalive = millis();
        if (!stream_active) {
          stream_active = true;
          Serial.printf("[UDPStream] Client %s:%u registered\n",
                        udp_stream_rx.remoteIP().toString().c_str(),
                        stream_client_port);
        }
      } else if (strcmp(cmd, "STREAM_STOP") == 0) {
        stream_active = false;
        Serial.println("[UDPStream] Client stopped");
      }
    }
  }

  // --- Forward UDP packets from Godot → Arduino serial -----------------------
  // Drain all pending servo packets — only forward the latest per-channel.
  // At 4800 baud, each 6-byte command takes ~12ms. Flushing prevents TX buffer
  // buildup that causes the Arduino to execute stale positions.
  int packet_size = udp.parsePacket();
  while (packet_size > 0) {
    char buf[64];
    int len = udp.read(buf, sizeof(buf) - 1);
    if (len > 0) {
      buf[len] = '\0';
      Serial.printf("[FWD] %s", buf);    // debug echo on USB serial
      ArduinoSerial.print(buf);          // forward "<ch>,<angle>\n" to Arduino
      ArduinoSerial.flush();             // wait for UART TX to drain
    }
    packet_size = udp.parsePacket();
  }

  // Echo Arduino responses (OK/ERR) to USB debug serial
  while (ArduinoSerial.available()) {
    Serial.write(ArduinoSerial.read());
  }
}
