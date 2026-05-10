/**
 * PrinterScene — Three.js 3D scene for the Lego-pusher digital shadow.
 *
 * Renders:
 *   - Build plate (the bed surface)
 *   - Build volume wireframe
 *   - Actuator (the tool head) as a cylinder + cone
 *   - Grid helper on the bed plane
 *
 * Coordinate mapping (same as Godot visualizer):
 *   Printer X → Three X
 *   Printer Y → Three Z  (depth)
 *   Printer Z → Three Y  (height)
 *
 * Scale: 1 Three unit = 1 mm  (actual size for precision)
 */

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh, Group } from "three";
import * as THREE from "three";
import type { BedConfig, PrinterState } from "./usePrinterState.ts";

interface Props {
  state: PrinterState;
  bed: BedConfig;
}

/** Smoothly interpolated actuator position */
function Actuator({ state }: { state: PrinterState }) {
  const groupRef = useRef<Group>(null);
  const targetRef = useRef({ x: 0, y: 0, z: 0 });

  // Update target whenever state has valid coordinates
  if (state.x != null) targetRef.current.x = state.x;
  if (state.z != null) targetRef.current.y = state.z; // printer Z → Three Y
  if (state.y != null) targetRef.current.z = state.y; // printer Y → Three Z

  useFrame((_frameState, delta) => {
    if (!groupRef.current) return;
    const t = targetRef.current;
    const p = groupRef.current.position;
    const lerp = 1 - Math.pow(0.001, delta); // smooth ~60 fps
    p.x += (t.x - p.x) * lerp;
    p.y += (t.y - p.y) * lerp;
    p.z += (t.z - p.z) * lerp;
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

export default function PrinterScene({ state, bed }: Props) {
  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[200, 300, 150]} intensity={0.8} />
      <directionalLight position={[-100, 200, -100]} intensity={0.3} />

      <BuildPlate bed={bed} />
      <BedGrid bed={bed} />
      <BuildVolume bed={bed} />
      <AxisIndicator />
      <Actuator state={state} />
    </>
  );
}
