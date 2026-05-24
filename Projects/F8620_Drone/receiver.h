// F8620 Quadcopter Drone — Receiver Input
// Captures PWM or PPM signals from the C3-7-RX receiver module.
#ifndef RECEIVER_H
#define RECEIVER_H

#include "config.h"

// Channel indices
enum RxChannel : uint8_t {
  CH_THROTTLE = 0,
  CH_YAW      = 1,
  CH_PITCH    = 2,
  CH_ROLL     = 3,
  CH_COUNT    = 4
};

// Raw pulse widths in microseconds (updated by ISRs)
static volatile uint16_t rx_pulse_us[CH_COUNT];
static volatile uint32_t rx_last_update_ms;

// Rise timestamps for PWM capture
static volatile uint32_t rx_rise_us[CH_COUNT];

// ============================================================================
//  PWM CAPTURE (individual channel mode)
// ============================================================================

#if USE_PPM_INPUT == 0

// Pin-change interrupt handler template for a single channel
static void rx_handle_pin(uint8_t ch, uint8_t pin) {
  uint32_t now = micros();
  if (digitalRead(pin) == HIGH) {
    rx_rise_us[ch] = now;
  } else {
    uint32_t width = now - rx_rise_us[ch];
    if (width >= 800 && width <= 2200) {
      rx_pulse_us[ch] = (uint16_t)width;
      rx_last_update_ms = millis();
    }
  }
}

// ISR for throttle (hardware interrupt on pin 2)
static void rx_isr_ch1() { rx_handle_pin(CH_THROTTLE, RX_CH1_PIN); }

// Pin-change ISR for channels on PORTD (pins 0–7)
ISR(PCINT2_vect) {
  rx_handle_pin(CH_YAW,   RX_CH2_PIN);
  rx_handle_pin(CH_PITCH, RX_CH3_PIN);
}

// Pin-change ISR for channels on PORTB (pins 8–13)
ISR(PCINT0_vect) {
  rx_handle_pin(CH_ROLL, RX_CH4_PIN);
}

static void rx_init() {
  // Initialize pulse values to center (throttle to minimum)
  rx_pulse_us[CH_THROTTLE] = RX_PULSE_MIN;
  rx_pulse_us[CH_YAW]      = RX_PULSE_MID;
  rx_pulse_us[CH_PITCH]    = RX_PULSE_MID;
  rx_pulse_us[CH_ROLL]     = RX_PULSE_MID;
  rx_last_update_ms = 0;

  // CH1 (throttle) on pin 2 — hardware INT0
  pinMode(RX_CH1_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(RX_CH1_PIN), rx_isr_ch1, CHANGE);

  // CH2 (yaw) on pin 4 — PCINT20 (PORTD)
  pinMode(RX_CH2_PIN, INPUT);
  PCICR  |= (1 << PCIE2);
  PCMSK2 |= (1 << PCINT20);  // pin 4

  // CH3 (pitch) on pin 7 — PCINT23 (PORTD)
  pinMode(RX_CH3_PIN, INPUT);
  PCMSK2 |= (1 << PCINT23);  // pin 7

  // CH4 (roll) on pin 8 — PCINT0 (PORTB)
  pinMode(RX_CH4_PIN, INPUT);
  PCICR  |= (1 << PCIE0);
  PCMSK0 |= (1 << PCINT0);   // pin 8
}

#else

// ============================================================================
//  PPM CAPTURE (combined signal on single wire)
// ============================================================================

static volatile uint8_t ppm_channel_index;
static volatile uint32_t ppm_last_edge_us;

static void rx_isr_ppm() {
  uint32_t now = micros();
  uint32_t width = now - ppm_last_edge_us;
  ppm_last_edge_us = now;

  if (width > 3000) {
    // Sync gap — reset channel counter
    ppm_channel_index = 0;
    rx_last_update_ms = millis();
  } else if (ppm_channel_index < PPM_NUM_CHANNELS) {
    if (width >= 800 && width <= 2200) {
      rx_pulse_us[ppm_channel_index] = (uint16_t)width;
    }
    ppm_channel_index++;
  }
}

static void rx_init() {
  rx_pulse_us[CH_THROTTLE] = RX_PULSE_MIN;
  rx_pulse_us[CH_YAW]      = RX_PULSE_MID;
  rx_pulse_us[CH_PITCH]    = RX_PULSE_MID;
  rx_pulse_us[CH_ROLL]     = RX_PULSE_MID;
  rx_last_update_ms = 0;
  ppm_channel_index = 0;
  ppm_last_edge_us = 0;

  pinMode(RX_CH1_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(RX_CH1_PIN), rx_isr_ppm, RISING);
}

#endif // USE_PPM_INPUT

// ============================================================================
//  Read channels with interrupts disabled (atomic copy)
// ============================================================================
static void rx_read(uint16_t out_us[CH_COUNT], bool &signal_valid) {
  noInterrupts();
  for (uint8_t i = 0; i < CH_COUNT; i++) {
    out_us[i] = rx_pulse_us[i];
  }
  uint32_t last = rx_last_update_ms;
  interrupts();

  signal_valid = (last > 0) && ((millis() - last) < RX_FAILSAFE_TIMEOUT_MS);
}

// Map a pulse (1000–2000µs) to a signed value (-500 to +500) with deadband
static int16_t rx_to_signed(uint16_t pulse_us) {
  int16_t centered = (int16_t)pulse_us - (int16_t)RX_PULSE_MID;
  if (centered > -(int16_t)RX_PULSE_DEADBAND &&
      centered < (int16_t)RX_PULSE_DEADBAND) {
    return 0;
  }
  return constrain(centered, -500, 500);
}

// Map throttle pulse (1000–2000µs) to 0–1000
static int16_t rx_to_throttle(uint16_t pulse_us) {
  return constrain((int16_t)pulse_us - (int16_t)RX_PULSE_MIN, 0, 1000);
}

#endif // RECEIVER_H
