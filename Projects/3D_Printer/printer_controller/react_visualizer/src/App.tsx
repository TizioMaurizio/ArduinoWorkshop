/**
 * App — Root component for the Lego Pusher digital shadow.
 *
 * Connects to the Python backend via WebSocket, receives actuator
 * position, and renders a 3D visualization.  Keyboard presses send
 * jog commands to the Python backend via REST API — all safety
 * validation happens server-side.
 */

import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import PrinterScene from "./PrinterScene.tsx";
import StatusOverlay from "./StatusOverlay.tsx";
import ControlsOverlay from "./ControlsOverlay.tsx";
import { usePrinterState } from "./usePrinterState.ts";
import { useKeyboardJog } from "./useKeyboardJog.ts";

export default function App() {
  const { state, bed, wsStatus } = usePrinterState();
  const jog = useKeyboardJog();

  // Camera looks at center of bed from an elevated angle
  const cx = (bed.x_min + bed.x_max) / 2;
  const cz = (bed.y_min + bed.y_max) / 2;

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
        />
        <PrinterScene state={state} bed={bed} />
      </Canvas>
      <StatusOverlay state={state} wsStatus={wsStatus} />
      <ControlsOverlay jog={jog} />
    </div>
  );
}
