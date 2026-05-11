/**
 * App — Root component for the Lego Pusher digital shadow.
 *
 * Connects to the Python backend via WebSocket, receives actuator
 * position, and renders a 3D visualization.  Keyboard presses move
 * the predicted actuator instantly; coalesced commands are sent to the
 * backend at a throttled interval to avoid USB saturation.
 */

import { useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import PrinterScene from "./PrinterScene.tsx";
import StatusOverlay from "./StatusOverlay.tsx";
import ControlsOverlay from "./ControlsOverlay.tsx";
import MouseControl from "./MouseControl.tsx";
import { usePrinterState } from "./usePrinterState.ts";
import { useActuatorControl } from "./useActuatorControl.ts";

export default function App() {
  const { state, bed, wsStatus, sendTarget } = usePrinterState();
  const ctrl = useActuatorControl(state, bed, sendTarget);
  const [mouseMode, setMouseMode] = useState(false);

  // Camera looks at center of bed from an elevated angle
  const cx = (bed.x_min + bed.x_max) / 2;
  const cz = (bed.y_min + bed.y_max) / 2;

  // Adapt ControlsOverlay to the JogState interface it expects
  const jogState = {
    xyStep: ctrl.xyStep,
    zStep: ctrl.zStep,
    xyStepIdx: 0,
    zStepIdx: 0,
    lastAction: ctrl.lastAction,
  };

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <Canvas
        camera={{
          position: [cx + 250, 300, cz + 250],
          fov: 45,
          near: 1,
          far: 2000,
        }}
      >
        <color attach="background" args={["#0a0a14"]} />
        <fog attach="fog" args={["#0a0a14", 400, 1200]} />
        <OrbitControls
          target={[cx, 40, cz]}
          enableDamping
          dampingFactor={0.15}
          minDistance={50}
          maxDistance={800}
          maxPolarAngle={Math.PI / 2 - 0.05}
          enabled={!mouseMode}
        />
        <PrinterScene
          state={state}
          bed={bed}
          predictedRef={ctrl.predictedRef}
          actualRef={ctrl.actualRef}
          advancePredicted={ctrl.advancePredicted}
          hasPending={ctrl.hasPending}
        />
        <MouseControl
          bed={bed}
          predictedRef={ctrl.predictedRef}
          userActiveRef={ctrl.userActiveRef}
          targetDirtyRef={ctrl.targetDirtyRef}
          enabled={mouseMode}
        />
      </Canvas>
      <StatusOverlay state={state} wsStatus={wsStatus} />
      <ControlsOverlay jog={jogState} />
      <button
        onClick={() => setMouseMode((m) => !m)}
        style={{
          position: "absolute",
          bottom: 16,
          left: 16,
          padding: "10px 18px",
          background: mouseMode ? "#4488ff" : "rgba(30, 30, 50, 0.85)",
          color: mouseMode ? "#fff" : "#aab",
          border: mouseMode ? "2px solid #6aa8ff" : "1px solid rgba(80, 80, 120, 0.5)",
          borderRadius: 8,
          cursor: "pointer",
          fontFamily: "'Consolas', monospace",
          fontSize: 13,
          fontWeight: 600,
          backdropFilter: "blur(6px)",
          transition: "all 0.15s ease",
        }}
      >
        {mouseMode ? "🖱 Mouse Control ON" : "🖱 Mouse Control"}
      </button>
    </div>
  );
}
