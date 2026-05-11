/**
 * useActuatorControl — smooth continuous actuator controller.
 *
 * Architecture:
 *   1. While a movement key is HELD, the target position moves
 *      continuously at the configured speed (mm/s)
 *   2. The 3D scene renders the target position instantly
 *   3. Every TICK_MS, the current target is sent to Python via WebSocket
 *   4. Python's follower loop sends ONE absolute G1 move per tick
 *   5. Marlin replans smoothly — no stop-start stutter
 *   6. WebSocket delivers actual position back for the ghost actuator
 *
 * Geeetech A10 parameters:
 *   - Max feedrate XY: 300 mm/s (F18000), Z: 5 mm/s (F300)
 *   - Jog speed: configurable per step size (slower = more precise)
 *   - TICK_MS=200 → 5 target updates/s, well within capacity
 */

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import * as api from "./api.ts";
import type { BedConfig, PrinterState } from "./usePrinterState.ts";

// ── Tuning constants ────────────────────────────────────────────────────

/** How often to send the current target to the backend (ms). */
const TICK_MS = 100;

/** Speed in mm/s for continuous movement while a key is held. */
const XY_SPEED_MM_S = 50;
const Z_SPEED_MM_S = 5;

/**
 * When no keys are pressed, predicted position converges toward actual
 * using exponential decay. Rate=2.0 closes ~86% of the gap per second.
 */

/** If predicted diverges from actual by more than this, snap faster. */
const SNAP_THRESHOLD_MM = 50;

// ── Step tables (for single taps) ───────────────────────────────────────

const XY_STEPS = [0.1, 0.5, 1, 5, 10, 50];
const Z_STEPS = [0.05, 0.1, 0.5, 1, 5, 10];

// ── Types ───────────────────────────────────────────────────────────────

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface ActuatorControlState {
  /** Mutable ref — read in useFrame for 60fps updates, never causes re-render. */
  predictedRef: MutableRefObject<Vec3>;
  /** Mutable ref — read in useFrame for 60fps updates. */
  actualRef: MutableRefObject<Vec3>;
  hasPending: boolean;
  xyStep: number;
  zStep: number;
  lastAction: string;
}

// ── Hook ────────────────────────────────────────────────────────────────

export function useActuatorControl(
  printerState: PrinterState,
  bed: BedConfig,
  sendTarget: (x: number, y: number, z: number) => void,
) {
  const [xyStepIdx, setXyStepIdx] = useState(2);
  const [zStepIdx, setZStepIdx] = useState(1);
  const [lastAction, setLastAction] = useState("");
  const flashTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Predicted (target) position — rendered instantly
  const predictedRef = useRef<Vec3>({ x: 0, y: 0, z: 0 });
  // Actual position — from WebSocket
  const actualRef = useRef<Vec3>({ x: 0, y: 0, z: 0 });
  // Currently held keys
  const keysDown = useRef<Set<string>>(new Set());
  // Whether user is actively moving (keys held or recent tap)
  const userActiveRef = useRef(false);
  // Whether we've seeded from the first real position
  const initializedRef = useRef(false);
  // Whether target changed since last WS send
  const targetDirtyRef = useRef(false);

  const [, forceRender] = useState(0);
  const bump = useCallback(() => forceRender((n) => n + 1), []);

  const flash = useCallback((msg: string) => {
    setLastAction(msg);
    clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setLastAction(""), 2000);
  }, []);

  // ── Clamp to bed limits ───────────────────────────────────────────

  const clamp = useCallback(
    (p: Vec3): Vec3 => ({
      x: Math.max(bed.x_min, Math.min(bed.x_max, p.x)),
      y: Math.max(bed.y_min, Math.min(bed.y_max, p.y)),
      z: Math.max(bed.z_min, Math.min(bed.z_max, p.z)),
    }),
    [bed],
  );

  // ── Sync actual position from WebSocket (ref only, no re-render) ──

  useEffect(() => {
    const a = actualRef.current;
    if (printerState.x != null) a.x = printerState.x;
    if (printerState.y != null) a.y = printerState.y;
    if (printerState.z != null) a.z = printerState.z;

    if (!initializedRef.current && printerState.x != null) {
      initializedRef.current = true;
      predictedRef.current = { ...a };
    }
    // Reconciliation now happens in advancePredicted (60fps, time-based)
  }, [printerState.x, printerState.y, printerState.z]);

  // ── Animation loop: move target while keys are held ───────────────
  // This runs inside Three.js's own render loop via useFrame in
  // PrinterScene, so we DON'T need requestAnimationFrame here.
  // Instead we expose a tick function called from useFrame.

  // Advance predicted position based on held keys + reconcile toward actual.
  // Called from useFrame at 60fps — never triggers React re-renders.
  const advancePredicted = useCallback(
    (dt: number) => {
      const keys = keysDown.current;
      const p = predictedRef.current;

      if (keys.size > 0) {
        // ── Active movement ──────────────────────────────────────
        let moved = false;
        if (keys.has("d")) { p.x += XY_SPEED_MM_S * dt; moved = true; }
        if (keys.has("a")) { p.x -= XY_SPEED_MM_S * dt; moved = true; }
        if (keys.has("w") && !keys.has("shift")) { p.y += XY_SPEED_MM_S * dt; moved = true; }
        if (keys.has("s") && !keys.has("shift")) { p.y -= XY_SPEED_MM_S * dt; moved = true; }
        if (keys.has("w") && keys.has("shift")) { p.z += Z_SPEED_MM_S * dt; moved = true; }
        if (keys.has("s") && keys.has("shift")) { p.z -= Z_SPEED_MM_S * dt; moved = true; }

        if (moved) {
          const c = clamp(p);
          p.x = c.x; p.y = c.y; p.z = c.z;
          targetDirtyRef.current = true;
          userActiveRef.current = true;
        }
      } else if (!userActiveRef.current) {
        // ── Smooth reconciliation toward actual (time-based) ────
        // Only reconcile when the printer has actually reached (or
        // passed) the predicted position.  If it's still traveling
        // toward predicted, leave predicted alone — don't pull it back.
        const a = actualRef.current;
        const dx = a.x - p.x;
        const dy = a.y - p.y;
        const dz = a.z - p.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist > SNAP_THRESHOLD_MM) {
          // Something is very wrong (e.g. after homing) — snap fast
          const t = 1 - Math.exp(-8.0 * dt);
          p.x += dx * t;
          p.y += dy * t;
          p.z += dz * t;
        } else if (dist < 2.0) {
          // Printer has arrived close to target — gently converge
          const t = 1 - Math.exp(-3.0 * dt);
          p.x += dx * t;
          p.y += dy * t;
          p.z += dz * t;
        }
        // else: dist is 2–50mm → printer still traveling, don't pull back
      }
    },
    [clamp],
  );

  // ── Tick: send target to backend via WebSocket ────────────────────

  useEffect(() => {
    const interval = setInterval(() => {
      if (!targetDirtyRef.current) {
        // If no keys held, allow reconciliation
        if (keysDown.current.size === 0) {
          userActiveRef.current = false;
        }
        return;
      }
      targetDirtyRef.current = false;
      const p = predictedRef.current;
      sendTarget(p.x, p.y, p.z);
    }, TICK_MS);

    return () => clearInterval(interval);
  }, [sendTarget]);

  // ── Keyboard handler ──────────────────────────────────────────────

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      const key = e.key.toLowerCase();

      if (key === " " || key === "+" || key === "=" || key === "-") {
        e.preventDefault();
      }

      // Track shift state
      if (e.shiftKey) keysDown.current.add("shift");

      // Movement keys — add to held set
      if (["w", "a", "s", "d"].includes(key)) {
        if (!keysDown.current.has(key)) {
          keysDown.current.add(key);
          // Flash on first press
          if (key === "w") flash(e.shiftKey ? "Z +" : "Y +");
          if (key === "s") flash(e.shiftKey ? "Z −" : "Y −");
          if (key === "a") flash("X −");
          if (key === "d") flash("X +");
        }
        return;
      }

      // Non-movement keys
      switch (key) {
        case "h":
          predictedRef.current = { x: 0, y: 0, z: 0 };
          targetDirtyRef.current = false;
          userActiveRef.current = false;
          api.homeAll().then((r) => {
            if (!r.ok) flash(`ERR: ${r.error}`);
          });
          flash("Homing all axes");
          bump();
          break;
        case "p":
          api.getPosition();
          flash("Query position");
          break;
        case "t":
          api.getTemperature();
          flash("Query temperature");
          break;
        case " ":
          keysDown.current.clear();
          predictedRef.current = { ...actualRef.current };
          targetDirtyRef.current = false;
          userActiveRef.current = false;
          api.emergencyStop();
          flash("⚠ EMERGENCY STOP");
          bump();
          break;
        case "+":
        case "=":
          setXyStepIdx((i) => {
            const next = Math.min(i + 1, XY_STEPS.length - 1);
            flash(`XY step: ${XY_STEPS[next]} mm`);
            return next;
          });
          setZStepIdx((i) => Math.min(i + 1, Z_STEPS.length - 1));
          break;
        case "-":
          setXyStepIdx((i) => {
            const next = Math.max(i - 1, 0);
            flash(`XY step: ${XY_STEPS[next]} mm`);
            return next;
          });
          setZStepIdx((i) => Math.max(i - 1, 0));
          break;
      }
    }

    function onKeyUp(e: KeyboardEvent) {
      const key = e.key.toLowerCase();
      keysDown.current.delete(key);
      if (!e.shiftKey) keysDown.current.delete("shift");

      // If all movement keys released, send one final target and let
      // the predicted position start reconciling toward actual
      if (!keysDown.current.has("w") && !keysDown.current.has("a") &&
          !keysDown.current.has("s") && !keysDown.current.has("d")) {
        if (targetDirtyRef.current) {
          const p = predictedRef.current;
          sendTarget(p.x, p.y, p.z);
          targetDirtyRef.current = false;
        }
      }
    }

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [flash, bump, sendTarget]);

  // ── Return ────────────────────────────────────────────────────────

  return {
    predictedRef,
    actualRef,
    userActiveRef,
    targetDirtyRef,
    advancePredicted,
    hasPending: targetDirtyRef.current || keysDown.current.size > 0,
    xyStep: XY_STEPS[xyStepIdx],
    zStep: Z_STEPS[zStepIdx],
    lastAction,
  };
}
