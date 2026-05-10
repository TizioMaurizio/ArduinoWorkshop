/**
 * usePrinterState — WebSocket hook that receives live printer state
 * from the Python backend.  Read-only: never sends commands.
 */

import { useEffect, useRef, useState } from "react";

const WS_URL = "ws://127.0.0.1:8765/ws/state";
const RECONNECT_DELAY_MS = 3_000;

export interface BedConfig {
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  z_min: number;
  z_max: number;
}

export interface PrinterState {
  connected: boolean;
  firmware: string | null;
  x: number | null;
  y: number | null;
  z: number | null;
  e: number | null;
  homed_x: boolean;
  homed_y: boolean;
  homed_z: boolean;
  hotend_temp_c: number | null;
  hotend_target_c: number | null;
  bed_temp_c: number | null;
  bed_target_c: number | null;
  busy: boolean;
  locked: boolean;
  last_error: string | null;
}

const DEFAULT_STATE: PrinterState = {
  connected: false,
  firmware: null,
  x: null,
  y: null,
  z: null,
  e: null,
  homed_x: false,
  homed_y: false,
  homed_z: false,
  hotend_temp_c: null,
  hotend_target_c: null,
  bed_temp_c: null,
  bed_target_c: null,
  busy: false,
  locked: false,
  last_error: null,
};

const DEFAULT_BED: BedConfig = {
  x_min: 0,
  x_max: 220,
  y_min: 0,
  y_max: 220,
  z_min: 0,
  z_max: 250,
};

export type WsStatus = "connecting" | "connected" | "disconnected";

export function usePrinterState() {
  const [state, setState] = useState<PrinterState>(DEFAULT_STATE);
  const [bed, setBed] = useState<BedConfig>(DEFAULT_BED);
  const [wsStatus, setWsStatus] = useState<WsStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    let mounted = true;

    function connect() {
      if (!mounted) return;
      setWsStatus("connecting");

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mounted) return;
        setWsStatus("connected");
      };

      ws.onmessage = (evt) => {
        if (!mounted) return;
        try {
          const data = JSON.parse(evt.data);
          if (data.type === "state") {
            setState({
              connected: data.connected ?? false,
              firmware: data.firmware ?? null,
              x: data.x ?? null,
              y: data.y ?? null,
              z: data.z ?? null,
              e: data.e ?? null,
              homed_x: data.homed_x ?? false,
              homed_y: data.homed_y ?? false,
              homed_z: data.homed_z ?? false,
              hotend_temp_c: data.hotend_temp_c ?? null,
              hotend_target_c: data.hotend_target_c ?? null,
              bed_temp_c: data.bed_temp_c ?? null,
              bed_target_c: data.bed_target_c ?? null,
              busy: data.busy ?? false,
              locked: data.locked ?? false,
              last_error: data.last_error ?? null,
            });
            // First message carries bed config
            if (data.bed) {
              setBed(data.bed);
            }
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (!mounted) return;
        setWsStatus("disconnected");
        wsRef.current = null;
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      };

      ws.onerror = () => {
        // onclose will fire after this
        ws.close();
      };
    }

    connect();

    return () => {
      mounted = false;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  return { state, bed, wsStatus };
}
