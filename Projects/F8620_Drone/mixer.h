// F8620 Quadcopter Drone — Motor Mixer
// Converts throttle/yaw/pitch/roll commands into 4 individual motor outputs.
//
// Motor layout (from PowerPoint — top view, front up):
//
//        FRONT
//    M1 (CW)   M4 (CCW)
//        \     /
//         \   /
//          X
//         / \
//        /   \
//    M2 (CCW)  M3 (CW)
//        REAR
//
// Mixing rules (derived from F8620 presentation, slides 14–17):
//   Throttle up:  all motors increase equally
//   Pitch fwd:    rear (M2,M3) increase, front (M1,M4) decrease
//   Roll left:    right (M3,M4) increase, left (M1,M2) decrease
//   Yaw left:     CCW motors (M2,M4) increase, CW motors (M1,M3) decrease
//
#ifndef MIXER_H
#define MIXER_H

#include "config.h"

// Motor output array — index matches motor number (0=M1, 1=M2, 2=M3, 3=M4)
enum MotorIndex : uint8_t {
  MOTOR_M1 = 0,  // front-left,  CW
  MOTOR_M2 = 1,  // rear-left,   CCW
  MOTOR_M3 = 2,  // rear-right,  CW
  MOTOR_M4 = 3,  // front-right, CCW
  MOTOR_COUNT = 4
};

static const uint8_t motor_pins[MOTOR_COUNT] = {
  PIN_MOTOR_M1, PIN_MOTOR_M2, PIN_MOTOR_M3, PIN_MOTOR_M4
};

static void mixer_init() {
  for (uint8_t i = 0; i < MOTOR_COUNT; i++) {
    pinMode(motor_pins[i], OUTPUT);
    analogWrite(motor_pins[i], 0);
  }
}

// Compute motor outputs from control inputs.
//   throttle: 0–1000 (0 = off, 1000 = max)
//   yaw:      -500 to +500 (positive = yaw right)
//   pitch:    -500 to +500 (positive = pitch forward / nose down)
//   roll:     -500 to +500 (positive = roll right)
//
// Output written to motor_out[0..3] as 0–255 PWM values.
static void mixer_compute(int16_t throttle, int16_t yaw, int16_t pitch,
                           int16_t roll, uint8_t motor_out[MOTOR_COUNT]) {
  // Scale throttle from 0–1000 to 0–255 range
  int16_t thr = (int32_t)throttle * MOTOR_PWM_MAX / 1000;

  // Scale control axes: ±500 → ±127 (half of PWM range for mixing headroom)
  int16_t p = (int32_t)pitch * 127 / 500;
  int16_t r = (int32_t)roll  * 127 / 500;
  int16_t y = (int32_t)yaw   * 127 / 500;

  // Quadcopter X-configuration mixing
  //   M1 (front-left,  CW):  +throttle  -pitch  -roll  -yaw
  //   M2 (rear-left,   CCW): +throttle  +pitch  -roll  +yaw
  //   M3 (rear-right,  CW):  +throttle  +pitch  +roll  -yaw
  //   M4 (front-right, CCW): +throttle  -pitch  +roll  +yaw
  int16_t mix[MOTOR_COUNT];
  mix[MOTOR_M1] = thr - p - r - y;
  mix[MOTOR_M2] = thr + p - r + y;
  mix[MOTOR_M3] = thr + p + r - y;
  mix[MOTOR_M4] = thr - p + r + y;

  for (uint8_t i = 0; i < MOTOR_COUNT; i++) {
    // Clamp to valid PWM range
    if (mix[i] < 0) mix[i] = 0;
    if (mix[i] > MOTOR_PWM_MAX) mix[i] = MOTOR_PWM_MAX;

    // Apply minimum idle speed when armed and throttle is nonzero
    if (throttle > MOTOR_ARM_THRESHOLD && mix[i] < MOTOR_PWM_IDLE) {
      mix[i] = MOTOR_PWM_IDLE;
    }

    motor_out[i] = (uint8_t)mix[i];
  }
}

// Write computed PWM values to motor pins
static void mixer_write(const uint8_t motor_out[MOTOR_COUNT]) {
  for (uint8_t i = 0; i < MOTOR_COUNT; i++) {
    analogWrite(motor_pins[i], motor_out[i]);
  }
}

// Emergency stop — all motors off immediately
static void mixer_kill() {
  for (uint8_t i = 0; i < MOTOR_COUNT; i++) {
    analogWrite(motor_pins[i], 0);
  }
}

#endif // MIXER_H
