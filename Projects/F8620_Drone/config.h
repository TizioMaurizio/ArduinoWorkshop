// F8620 Quadcopter Drone — Configuration
// Target board: Arduino Nano (ATmega328P) or Arduino Uno
// RAM budget: ~1.2 KB used of 2 KB available
// Compile with: -Wall -Wextra
#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ============================================================================
//  MOTOR PIN DEFINITIONS
//  F8620 uses 4x coreless brushed motors (8.6mm x 20mm), driven via
//  N-channel MOSFETs or SI2302 transistors from PWM-capable pins.
//
//  Motor layout (top view, front = arrow direction):
//
//        FRONT
//    M1 (CW)   M4 (CCW)
//        \     /
//         \   /
//          \ /
//          / \
//         /   \
//        /     \
//    M2 (CCW)  M3 (CW)
//        REAR
//
//  CW  = clockwise propeller   (M1, M3)
//  CCW = counterclockwise prop  (M2, M4)
// ============================================================================
static const uint8_t PIN_MOTOR_M1 = 3;   // front-left,  CW   (PWM)
static const uint8_t PIN_MOTOR_M2 = 9;   // rear-left,   CCW  (PWM)
static const uint8_t PIN_MOTOR_M3 = 10;  // rear-right,  CW   (PWM)
static const uint8_t PIN_MOTOR_M4 = 11;  // front-right, CCW  (PWM)

// ============================================================================
//  RECEIVER INPUT PINS
//  Connect the C3-7-RX receiver output channels here.
//  These must support pin-change interrupts (all digital pins on Nano).
//  If using combined PPM, connect only RX_CH1_PIN and set USE_PPM_INPUT.
// ============================================================================
static const uint8_t RX_CH1_PIN = 2;  // Throttle  (INT0, hardware interrupt)
static const uint8_t RX_CH2_PIN = 4;  // Yaw
static const uint8_t RX_CH3_PIN = 7;  // Pitch
static const uint8_t RX_CH4_PIN = 8;  // Roll

// Set to 1 for combined PPM on a single wire (RX_CH1_PIN only)
// Set to 0 for individual PWM per channel (one wire per channel)
#define USE_PPM_INPUT 0

// Number of PPM channels to decode (only used if USE_PPM_INPUT == 1)
#define PPM_NUM_CHANNELS 4

// ============================================================================
//  RECEIVER SIGNAL PARAMETERS
// ============================================================================
static const uint16_t RX_PULSE_MIN   = 1000;  // microseconds — stick fully low/left
static const uint16_t RX_PULSE_MID   = 1500;  // microseconds — stick centered
static const uint16_t RX_PULSE_MAX   = 2000;  // microseconds — stick fully high/right
static const uint16_t RX_PULSE_DEADBAND = 30; // microseconds — ignore noise around center
static const uint16_t RX_FAILSAFE_TIMEOUT_MS = 500; // no signal → kill motors

// ============================================================================
//  MOTOR OUTPUT PARAMETERS
// ============================================================================
static const uint8_t MOTOR_PWM_MIN     = 0;    // motors off
static const uint8_t MOTOR_PWM_IDLE    = 30;   // minimum spin when armed (prevents stall)
static const uint8_t MOTOR_PWM_MAX     = 255;  // full throttle (8-bit PWM)
static const uint8_t MOTOR_ARM_THRESHOLD = 10; // throttle must be below this to arm

// ============================================================================
//  ARMING
//  Throttle low + Yaw right for ARM_HOLD_MS → armed
//  Throttle low + Yaw left  for ARM_HOLD_MS → disarmed
// ============================================================================
static const uint16_t ARM_HOLD_MS = 1000;

// ============================================================================
//  CONTROL LOOP
// ============================================================================
static const uint16_t LOOP_INTERVAL_US = 4000;  // 250 Hz control loop

// ============================================================================
//  SERIAL CONTROL MODE
//  If no receiver is connected, commands can be sent over Serial at 115200.
//  Format: "T<throttle> Y<yaw> P<pitch> R<roll>\n"
//  Values: -500 to +500 (0 = center, except throttle: 0–1000)
// ============================================================================
static const uint32_t SERIAL_BAUD = 115200;
static const uint16_t SERIAL_TIMEOUT_MS = 300;  // no serial → kill motors

// ============================================================================
//  STATUS LED
// ============================================================================
static const uint8_t PIN_LED = 13;  // built-in LED for status indication

#endif // CONFIG_H
