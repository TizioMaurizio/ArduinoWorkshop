/**
 * api.ts — thin wrapper around the Python backend REST API.
 *
 * All safety validation happens server-side in Python.
 * This module only forwards user intent.
 */

const BASE = "http://127.0.0.1:8765";

export interface ApiResult {
  ok: boolean;
  error?: string;
  data?: Record<string, unknown>;
}

async function post(path: string, body?: object): Promise<ApiResult> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json();
    if (data.error) {
      return { ok: false, error: data.error, data };
    }
    return { ok: true, data };
  } catch (err) {
    const msg =
      err instanceof TypeError
        ? "Cannot reach backend — is it running? (restart needed for CORS)"
        : String(err);
    return { ok: false, error: msg };
  }
}

export function jog(axis: string, distance_mm: number): Promise<ApiResult> {
  return post("/jog", { axis, distance_mm });
}

export function homeAll(): Promise<ApiResult> {
  return post("/home");
}

export function homeAxis(axis: string): Promise<ApiResult> {
  return post(`/home?axis=${encodeURIComponent(axis)}`);
}

export function emergencyStop(): Promise<ApiResult> {
  return post("/emergency-stop");
}

export function getPosition(): Promise<ApiResult> {
  return post("/gcode", { command: "M114" });
}

export function getTemperature(): Promise<ApiResult> {
  return post("/gcode", { command: "M105" });
}
