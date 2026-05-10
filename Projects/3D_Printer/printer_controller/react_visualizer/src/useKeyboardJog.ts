/**
 * useKeyboardJog — captures keyboard presses for jog control.
 *
 * Sends commands to the Python backend via REST API.
 * All safety validation happens server-side.
 *
 * Controls:
 *   W/S         → Y +/-
 *   A/D         → X -/+
 *   Shift+W/S   → Z +/-
 *   H           → Home all
 *   P           → Query position (M114)
 *   T           → Query temperature (M105)
 *   +/=  -      → Increase / decrease step size
 *   Space       → Emergency stop
 */

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api.ts";
import type { ApiResult } from "./api.ts";

const XY_STEPS = [0.1, 0.5, 1, 5, 10, 50];
const Z_STEPS = [0.05, 0.1, 0.5, 1, 5, 10];

export interface JogState {
  xyStep: number;
  zStep: number;
  xyStepIdx: number;
  zStepIdx: number;
  lastAction: string;
}

export function useKeyboardJog() {
  const [xyStepIdx, setXyStepIdx] = useState(2); // 1.0 mm
  const [zStepIdx, setZStepIdx] = useState(1);    // 0.1 mm
  const [lastAction, setLastAction] = useState("");
  const lastActionTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const flash = useCallback((msg: string) => {
    setLastAction(msg);
    clearTimeout(lastActionTimer.current);
    lastActionTimer.current = setTimeout(() => setLastAction(""), 2500);
  }, []);

  /** Send an API call and flash the result or error. */
  const send = useCallback(
    (label: string, call: Promise<ApiResult>) => {
      flash(label);
      call.then((r) => {
        if (!r.ok) flash(`ERR: ${r.error}`);
      });
    },
    [flash],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Don't capture when typing in an input
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      const key = e.key.toLowerCase();
      const shift = e.shiftKey;

      // Prevent browser defaults for space (scroll) and +/- (zoom)
      if (key === " " || key === "+" || key === "=" || key === "-") {
        e.preventDefault();
      }

      switch (key) {
        case "w":
          if (shift) {
            send(`Z +${Z_STEPS[zStepIdx]} mm`, api.jog("Z", Z_STEPS[zStepIdx]));
          } else {
            send(`Y +${XY_STEPS[xyStepIdx]} mm`, api.jog("Y", XY_STEPS[xyStepIdx]));
          }
          break;
        case "s":
          if (shift) {
            send(`Z ${-Z_STEPS[zStepIdx]} mm`, api.jog("Z", -Z_STEPS[zStepIdx]));
          } else {
            send(`Y ${-XY_STEPS[xyStepIdx]} mm`, api.jog("Y", -XY_STEPS[xyStepIdx]));
          }
          break;
        case "a":
          send(`X ${-XY_STEPS[xyStepIdx]} mm`, api.jog("X", -XY_STEPS[xyStepIdx]));
          break;
        case "d":
          send(`X +${XY_STEPS[xyStepIdx]} mm`, api.jog("X", XY_STEPS[xyStepIdx]));
          break;
        case "h":
          send("Homing all axes", api.homeAll());
          break;
        case "p":
          send("Query position", api.getPosition());
          break;
        case "t":
          send("Query temperature", api.getTemperature());
          break;
        case " ":
          send("⚠ EMERGENCY STOP", api.emergencyStop());
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

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [xyStepIdx, zStepIdx, flash, send]);

  return {
    xyStep: XY_STEPS[xyStepIdx],
    zStep: Z_STEPS[zStepIdx],
    xyStepIdx,
    zStepIdx,
    lastAction,
  } satisfies JogState;
}
