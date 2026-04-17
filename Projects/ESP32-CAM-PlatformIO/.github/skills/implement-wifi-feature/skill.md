---
name: implement-wifi-feature
description: Add or modify Wi-Fi functionality with config storage, retry strategy, watchdog-safe reconnect, and telemetry hooks.
---

# Implement Wi-Fi Feature

## When to Use
When adding Wi-Fi connectivity, MQTT, HTTP endpoints, OTA, mDNS, or any network feature to an ESP32/ESP8266 project.

## Steps

### 1. Audit Current Network Code
- Search for existing WiFi, MQTT, HTTP, or OTA code in the project.
- Check `platformio.ini` or build config for network-related libraries and flags.
- Check partition table — OTA requires a two-OTA-partition layout.
- Identify if credentials are hardcoded (must be moved to config).

### 2. Credential and Config Storage
- Never hardcode SSID, password, broker URL, API keys, or tokens.
- Use one of:
  - `config.h` (gitignored) with `config.example.h` committed
  - NVS key-value storage (ESP32) for runtime-configurable credentials
  - SPIFFS/LittleFS JSON config file
- Provide a provisioning flow (serial input, AP mode portal, or BLE config) if appropriate.

### 3. Connection State Machine
Implement a non-blocking WiFi manager:
```
IDLE → CONNECTING → CONNECTED → DISCONNECTED → RECONNECTING → CONNECTED
                                              → FAILED (after max retries)
```
- Use WiFi event callbacks, not blocking `waitForConnectResult()`.
- Exponential backoff on reconnect: 1s, 2s, 4s, 8s, capped at 30s.
- Feed the watchdog during reconnect attempts.
- Log state transitions to Serial (guarded by `#ifdef DEBUG`).

### 4. Feature Implementation
Depending on the feature:
- **MQTT**: Use PubSubClient or AsyncMqttClient. Handle disconnect/reconnect. Use QoS 1 for important messages. Buffer messages during disconnect if RAM allows.
- **HTTP Server**: Use ESPAsyncWebServer. Serve from SPIFFS/LittleFS. Handle concurrent requests safely.
- **OTA**: Verify partition layout supports OTA. Add progress callback. Handle interrupted updates gracefully. Reboot only after verified write.
- **mDNS**: Register after WiFi connected event. Re-register after reconnect.

### 5. Watchdog Safety
- Ensure no blocking loop exceeds the watchdog timeout (typically 5s on ESP32).
- In long operations (OTA download, large HTTP response), yield or feed WDT.
- If disabling WDT is the only option, document why and re-enable immediately after.

### 6. Telemetry Hooks
- Add optional telemetry: RSSI, free heap, uptime, reconnect count, last disconnect reason.
- Expose via MQTT status topic, HTTP `/status` endpoint, or Serial.
- Guard with a compile flag: `-D TELEMETRY_ENABLED`.

### 7. Test Plan
- **Host test**: state machine transitions with fake WiFi events.
- **On-device test**: connect, disconnect (pull antenna / toggle AP), verify reconnect.
- **OTA test**: successful update, interrupted update, rollback.

## Acceptance Criteria
- Credentials are not in version control.
- Connection handles disconnect and reconnects automatically.
- Watchdog does not trigger during normal operation.
- Feature compiles for all target ESP boards.
- State machine logs transitions for debugging.
