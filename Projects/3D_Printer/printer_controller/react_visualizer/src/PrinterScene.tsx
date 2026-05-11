/**
 * PrinterScene — Three.js 3D scene for the Lego-pusher digital shadow.
 *
 * Renders:
 *   - Build plate (the bed surface)
 *   - Build volume wireframe
 *   - Actuator predicted position (solid, moves instantly on keypress)
 *   - Actuator actual position (ghost, trails behind)
 *   - Grid helper on the bed plane
 *
 * Coordinate mapping (same as Godot visualizer):
 *   Printer X → Three X
 *   Printer Y → Three Z  (depth)
 *   Printer Z → Three Y  (height)
 *
 * Scale: 1 Three unit = 1 mm  (actual size for precision)
 */

import { useRef, type MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh, Group } from "three";
import * as THREE from "three";
import type { BedConfig, PrinterState } from "./usePrinterState.ts";
import type { Vec3 } from "./useActuatorControl.ts";

interface Props {
  state: PrinterState;
  bed: BedConfig;
  predictedRef: MutableRefObject<Vec3>;
  actualRef: MutableRefObject<Vec3>;
  advancePredicted: (dt: number) => void;
  hasPending: boolean;
}

/** Predicted actuator — solid, reads directly from ref at 60fps */
function Actuator({
  predictedRef,
  state,
}: {
  predictedRef: MutableRefObject<Vec3>;
  state: PrinterState;
}) {
  const groupRef = useRef<Group>(null);

  useFrame((_s, delta) => {
    if (!groupRef.current) return;
    const p = predictedRef.current;
    const pos = groupRef.current.position;
    // Target in Three coords
    const tx = p.x;
    const ty = p.z; // printer Z → Three Y
    const tz = p.y; // printer Y → Three Z
    // Very fast exponential lerp — dampens mouse jitter while
    // feeling instant for keyboard. ~95% converged in 1 frame at 60fps.
    const t = 1 - Math.exp(-30 * delta);
    pos.x += (tx - pos.x) * t;
    pos.y += (ty - pos.y) * t;
    pos.z += (tz - pos.z) * t;
  });

  const headColor = state.connected
    ? state.locked
      ? "#ff3333"
      : state.busy
        ? "#ffaa22"
        : "#44cc66"
    : "#666666";

  return (
    <group ref={groupRef}>
      {/* Actuator body — cylinder */}
      <mesh position={[0, 12, 0]}>
        <cylinderGeometry args={[4, 4, 24, 16]} />
        <meshStandardMaterial color="#aaaacc" metalness={0.6} roughness={0.3} />
      </mesh>
      {/* Actuator tip — cone pointing down */}
      <mesh position={[0, -2, 0]}>
        <coneGeometry args={[3, 8, 16]} />
        <meshStandardMaterial color={headColor} metalness={0.4} roughness={0.4} />
      </mesh>
      {/* Point indicator — small sphere at the exact tip */}
      <mesh position={[0, -6, 0]}>
        <sphereGeometry args={[1.5, 12, 12]} />
        <meshStandardMaterial
          color={headColor}
          emissive={headColor}
          emissiveIntensity={0.5}
        />
      </mesh>
    </group>
  );
}

/** Ghost actuator — semi-transparent, shows where the printer actually is */
function ActuatorGhost({ actualRef }: { actualRef: MutableRefObject<Vec3> }) {
  const groupRef = useRef<Group>(null);

  useFrame((_frameState, delta) => {
    if (!groupRef.current) return;
    const a = actualRef.current;
    const tx = a.x;
    const ty = a.z; // printer Z → Three Y
    const tz = a.y; // printer Y → Three Z
    const p = groupRef.current.position;
    // Smooth trailing — slower than prediction
    const lerp = 1 - Math.pow(0.005, delta);
    p.x += (tx - p.x) * lerp;
    p.y += (ty - p.y) * lerp;
    p.z += (tz - p.z) * lerp;
  });

  return (
    <group ref={groupRef}>
      <mesh position={[0, 12, 0]}>
        <cylinderGeometry args={[4, 4, 24, 16]} />
        <meshStandardMaterial
          color="#5599ff"
          transparent
          opacity={0.18}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[0, -2, 0]}>
        <coneGeometry args={[3, 8, 16]} />
        <meshStandardMaterial
          color="#5599ff"
          transparent
          opacity={0.25}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[0, -6, 0]}>
        <sphereGeometry args={[1.5, 12, 12]} />
        <meshStandardMaterial
          color="#5599ff"
          emissive="#5599ff"
          emissiveIntensity={0.3}
          transparent
          opacity={0.35}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

/** Bed surface */
function BuildPlate({ bed }: { bed: BedConfig }) {
  const width = bed.x_max - bed.x_min;
  const depth = bed.y_max - bed.y_min;
  const cx = bed.x_min + width / 2;
  const cz = bed.y_min + depth / 2;

  return (
    <mesh
      position={[cx, -0.5, cz]}
      rotation={[0, 0, 0]}
      receiveShadow
    >
      <boxGeometry args={[width, 1, depth]} />
      <meshStandardMaterial color="#1a1a2e" metalness={0.1} roughness={0.8} />
    </mesh>
  );
}

/** Grid on the bed surface */
function BedGrid({ bed }: { bed: BedConfig }) {
  const width = bed.x_max - bed.x_min;
  const depth = bed.y_max - bed.y_min;
  const size = Math.max(width, depth);
  const cx = bed.x_min + width / 2;
  const cz = bed.y_min + depth / 2;

  return (
    <gridHelper
      args={[size, Math.floor(size / 10), "#333355", "#222244"]}
      position={[cx, 0.1, cz]}
    />
  );
}

/** Build volume wireframe box */
function BuildVolume({ bed }: { bed: BedConfig }) {
  const width = bed.x_max - bed.x_min;
  const depth = bed.y_max - bed.y_min;
  const height = bed.z_max - bed.z_min;
  const cx = bed.x_min + width / 2;
  const cy = height / 2;
  const cz = bed.y_min + depth / 2;

  const ref = useRef<Mesh>(null);

  return (
    <lineSegments position={[cx, cy, cz]} ref={ref}>
      <edgesGeometry
        args={[new THREE.BoxGeometry(width, height, depth)]}
      />
      <lineBasicMaterial color="#334466" linewidth={1} />
    </lineSegments>
  );
}

/** Axis indicator at the origin */
function AxisIndicator() {
  return (
    <group>
      {/* X axis — red */}
      <arrowHelper args={[new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, 0), 30, 0xff4444, 6, 3]} />
      {/* Y axis (printer Z) — green */}
      <arrowHelper args={[new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 0), 30, 0x44ff44, 6, 3]} />
      {/* Z axis (printer Y) — blue */}
      <arrowHelper args={[new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, 0), 30, 0x4488ff, 6, 3]} />
    </group>
  );
}

export default function PrinterScene({
  state,
  bed,
  predictedRef,
  actualRef,
  advancePredicted,
  hasPending,
}: Props) {
  // Drive the predicted position from Three's own render loop (60fps)
  useFrame((_frameState, delta) => {
    advancePredicted(delta);
  });

  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[200, 300, 150]} intensity={0.8} />
      <directionalLight position={[-100, 200, -100]} intensity={0.3} />

      <BuildPlate bed={bed} />
      <BedGrid bed={bed} />
      <BuildVolume bed={bed} />
      <AxisIndicator />
      {hasPending && <ActuatorGhost actualRef={actualRef} />}
      <Actuator predictedRef={predictedRef} state={state} />
    </>
  );
}
