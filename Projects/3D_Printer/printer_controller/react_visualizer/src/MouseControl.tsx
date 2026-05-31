/**
 * MouseControl — invisible plane on the bed surface that captures
 * pointer events when mouse-control mode is active.
 *
 * Clicking/dragging on the bed sets the actuator target XY position.
 * Holding Ctrl while dragging controls Z (height) only via a vertical plane.
 */

import { useRef, useState, useEffect } from "react";
import type { Mesh } from "three";
import * as THREE from "three";
import { useThree } from "@react-three/fiber";
import type { BedConfig } from "./usePrinterState.ts";
import type { Vec3 } from "./useActuatorControl.ts";
import type { MutableRefObject } from "react";

interface Props {
  bed: BedConfig;
  predictedRef: MutableRefObject<Vec3>;
  userActiveRef: MutableRefObject<boolean>;
  targetDirtyRef: MutableRefObject<boolean>;
  enabled: boolean;
}

export default function MouseControl({ bed, predictedRef, userActiveRef, targetDirtyRef, enabled }: Props) {
  const planeRef = useRef<Mesh>(null);
  const vertPlaneRef = useRef<Mesh>(null);
  const draggingRef = useRef(false);
  const [ctrlHeld, setCtrlHeld] = useState(false);
  const { camera } = useThree();

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === "Control") setCtrlHeld(true); };
    const onKeyUp = (e: KeyboardEvent) => { if (e.key === "Control") setCtrlHeld(false); };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  const width = bed.x_max - bed.x_min;
  const depth = bed.y_max - bed.y_min;
  const height = bed.z_max - bed.z_min;
  const cx = bed.x_min + width / 2;
  const cz = bed.y_min + depth / 2;
  const cy = bed.z_min + height / 2;
  // Make capture plane 3x bed size so fast drags never escape
  const planeW = width * 3;
  const planeD = depth * 3;
  const planeH = height * 3;

  if (!enabled) return null;

  function handlePointerXY(e: any) {
    e.stopPropagation();
    const point = e.point as THREE.Vector3;
    // Three.js coords → printer coords: X=X, printer Y=Three Z
    const px = Math.max(bed.x_min, Math.min(bed.x_max, point.x));
    const py = Math.max(bed.y_min, Math.min(bed.y_max, point.z));

    // Write directly to the ref — useFrame reads it at 60fps
    predictedRef.current.x = px;
    predictedRef.current.y = py;
    // Signal that user is active so reconciliation doesn't fight us
    userActiveRef.current = true;
    targetDirtyRef.current = true;
  }

  function handlePointerZ(e: any) {
    e.stopPropagation();
    const point = e.point as THREE.Vector3;
    // Three.js Y → printer Z (height)
    const pz = Math.max(bed.z_min, Math.min(bed.z_max, point.y));

    predictedRef.current.z = pz;
    userActiveRef.current = true;
    targetDirtyRef.current = true;
  }

  const handlePointer = ctrlHeld ? handlePointerZ : handlePointerXY;

  // Vertical plane faces camera (rotated to face camera direction on XZ)
  const camDir = new THREE.Vector3();
  camera.getWorldDirection(camDir);
  const vertRotY = Math.atan2(camDir.x, camDir.z);

  return (
    <>
      {/* Horizontal bed plane — XY control */}
      <mesh
        ref={planeRef}
        position={[cx, 0.5, cz]}
        rotation={[-Math.PI / 2, 0, 0]}
        visible={!ctrlHeld}
        onPointerDown={(e) => {
          if (ctrlHeld) return;
          e.stopPropagation();
          draggingRef.current = true;
          (e.target as any).setPointerCapture?.(e.pointerId);
          handlePointerXY(e);
        }}
        onPointerMove={(e) => {
          if (draggingRef.current && !ctrlHeld) handlePointerXY(e);
        }}
        onPointerUp={(e) => {
          if (!draggingRef.current) return;
          e.stopPropagation();
          draggingRef.current = false;
          (e.target as any).releasePointerCapture?.(e.pointerId);
          setTimeout(() => { userActiveRef.current = false; }, 500);
        }}
      >
        <planeGeometry args={[planeW, planeD]} />
        <meshBasicMaterial
          color="#4488ff"
          transparent
          opacity={0.03}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>

      {/* Vertical plane facing camera — Z (height) control when Ctrl held */}
      <mesh
        ref={vertPlaneRef}
        position={[cx, cy, cz]}
        rotation={[0, vertRotY, 0]}
        visible={ctrlHeld}
        onPointerDown={(e) => {
          if (!ctrlHeld) return;
          e.stopPropagation();
          draggingRef.current = true;
          (e.target as any).setPointerCapture?.(e.pointerId);
          handlePointerZ(e);
        }}
        onPointerMove={(e) => {
          if (draggingRef.current && ctrlHeld) handlePointerZ(e);
        }}
        onPointerUp={(e) => {
          if (!draggingRef.current) return;
          e.stopPropagation();
          draggingRef.current = false;
          (e.target as any).releasePointerCapture?.(e.pointerId);
          setTimeout(() => { userActiveRef.current = false; }, 500);
        }}
      >
        <planeGeometry args={[planeW, planeH]} />
        <meshBasicMaterial
          color="#ff8844"
          transparent
          opacity={0.03}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
    </>
  );
}
