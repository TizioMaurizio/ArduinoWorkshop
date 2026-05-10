/**
 * StatusOverlay — HUD overlay showing connection status, position, and state.
 * Displayed on top of the 3D canvas.
 */

import type { PrinterState, WsStatus } from "./usePrinterState.ts";

interface Props {
  state: PrinterState;
  wsStatus: WsStatus;
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    position: "absolute",
    top: 12,
    left: 12,
    display: "flex",
    flexDirection: "column",
    gap: 6,
    pointerEvents: "none",
    userSelect: "none",
    fontFamily: "'Consolas', 'Courier New', monospace",
    fontSize: 13,
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
    marginBottom: 4,
  },
  row: {
    display: "flex",
    justifyContent: "space-between",
    gap: 16,
  },
  label: {
    color: "#889",
  },
  value: {
    color: "#dde",
    fontWeight: 600,
  },
};

function fmt(v: number | null, decimals = 2): string {
  return v != null ? v.toFixed(decimals) : "—";
}

function wsColor(status: WsStatus): string {
  switch (status) {
    case "connected":
      return "#44cc66";
    case "connecting":
      return "#ffaa22";
    case "disconnected":
      return "#ff4444";
  }
}

function stateColor(state: PrinterState): string {
  if (state.locked) return "#ff4444";
  if (state.busy) return "#ffaa22";
  if (state.connected) return "#44cc66";
  return "#666";
}

function stateText(state: PrinterState): string {
  if (state.locked) return `LOCKED: ${state.last_error ?? "unknown"}`;
  if (state.busy) return "Busy";
  if (state.connected) {
    const axes = ["X", "Y", "Z"].filter(
      (a) => state[`homed_${a.toLowerCase()}` as keyof PrinterState],
    );
    return `Ready — homed: ${axes.length ? axes.join(",") : "none"}`;
  }
  return "Disconnected";
}

export default function StatusOverlay({ state, wsStatus }: Props) {
  return (
    <div style={styles.container}>
      {/* Connection */}
      <div style={styles.card}>
        <div style={styles.title}>Connection</div>
        <div style={styles.row}>
          <span style={styles.label}>WebSocket</span>
          <span style={{ ...styles.value, color: wsColor(wsStatus) }}>
            {wsStatus}
          </span>
        </div>
        <div style={styles.row}>
          <span style={styles.label}>Printer</span>
          <span style={{ ...styles.value, color: stateColor(state) }}>
            {state.connected ? "Online" : "Offline"}
          </span>
        </div>
        {state.firmware && (
          <div style={styles.row}>
            <span style={styles.label}>Firmware</span>
            <span style={styles.value}>{state.firmware}</span>
          </div>
        )}
      </div>

      {/* State */}
      <div style={styles.card}>
        <div style={styles.title}>State</div>
        <div style={{ color: stateColor(state), fontWeight: 600 }}>
          {stateText(state)}
        </div>
      </div>

      {/* Position */}
      <div style={styles.card}>
        <div style={styles.title}>Actuator Position</div>
        <div style={styles.row}>
          <span style={{ ...styles.label, color: "#ff6666" }}>X</span>
          <span style={styles.value}>{fmt(state.x)} mm</span>
        </div>
        <div style={styles.row}>
          <span style={{ ...styles.label, color: "#66bb66" }}>Y</span>
          <span style={styles.value}>{fmt(state.y)} mm</span>
        </div>
        <div style={styles.row}>
          <span style={{ ...styles.label, color: "#6688ff" }}>Z</span>
          <span style={styles.value}>{fmt(state.z)} mm</span>
        </div>
      </div>
    </div>
  );
}
