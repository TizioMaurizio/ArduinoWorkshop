/**
 * ControlsOverlay — bottom-right HUD showing keyboard shortcuts,
 * current step sizes, and last action feedback.
 */

import type { JogState } from "./useKeyboardJog.ts";

interface Props {
  jog: JogState;
}

const s: Record<string, React.CSSProperties> = {
  wrap: {
    position: "absolute",
    bottom: 12,
    right: 12,
    display: "flex",
    flexDirection: "column",
    gap: 6,
    pointerEvents: "none",
    userSelect: "none",
    fontFamily: "'Consolas', 'Courier New', monospace",
    fontSize: 12,
    maxWidth: 240,
  },
  card: {
    background: "rgba(20, 20, 35, 0.85)",
    border: "1px solid rgba(80, 80, 120, 0.4)",
    borderRadius: 6,
    padding: "8px 12px",
    backdropFilter: "blur(6px)",
  },
  title: {
    fontSize: 11,
    fontWeight: 700,
    textTransform: "uppercase" as const,
    letterSpacing: 1.5,
    color: "#667",
    marginBottom: 6,
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    gap: 8,
    lineHeight: "1.6",
  },
  key: {
    color: "#aab",
    background: "rgba(60, 60, 90, 0.5)",
    borderRadius: 3,
    padding: "1px 5px",
    fontWeight: 700,
    fontSize: 11,
  },
  desc: {
    color: "#889",
    textAlign: "right" as const,
  },
  flash: {
    background: "rgba(85, 153, 255, 0.15)",
    border: "1px solid rgba(85, 153, 255, 0.5)",
    borderRadius: 6,
    padding: "6px 12px",
    color: "#8bf",
    fontWeight: 700,
    fontSize: 13,
    textAlign: "center" as const,
  },
  estopFlash: {
    background: "rgba(204, 34, 34, 0.25)",
    border: "1px solid rgba(255, 68, 68, 0.6)",
    borderRadius: 6,
    padding: "6px 12px",
    color: "#f44",
    fontWeight: 700,
    fontSize: 14,
    textAlign: "center" as const,
  },
  stepRow: {
    display: "flex",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 2,
  },
  stepLabel: { color: "#889" },
  stepVal: { color: "#dde", fontWeight: 600 },
};

const KEYS: [string, string][] = [
  ["W / S", "Y +/−"],
  ["A / D", "X −/+"],
  ["⇧W / ⇧S", "Z +/−"],
  ["H", "Home all"],
  ["P", "Get position"],
  ["T", "Get temp"],
  ["+  /  −", "Step size"],
  ["Space", "E-STOP"],
];

export default function ControlsOverlay({ jog }: Props) {
  return (
    <div style={s.wrap}>
      {/* Action flash */}
      {jog.lastAction && (
        <div
          style={
            jog.lastAction.includes("EMERGENCY") ? s.estopFlash : s.flash
          }
        >
          {jog.lastAction}
        </div>
      )}

      {/* Step sizes */}
      <div style={s.card}>
        <div style={s.title}>Step Size</div>
        <div style={s.stepRow}>
          <span style={s.stepLabel}>XY</span>
          <span style={s.stepVal}>{jog.xyStep} mm</span>
        </div>
        <div style={s.stepRow}>
          <span style={s.stepLabel}>Z</span>
          <span style={s.stepVal}>{jog.zStep} mm</span>
        </div>
      </div>

      {/* Keyboard legend */}
      <div style={s.card}>
        <div style={s.title}>Keyboard</div>
        {KEYS.map(([k, d]) => (
          <div key={k} style={s.row}>
            <span style={s.key}>{k}</span>
            <span style={s.desc}>{d}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
