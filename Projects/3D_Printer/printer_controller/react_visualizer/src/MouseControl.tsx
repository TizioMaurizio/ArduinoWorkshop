/**
 * MouseControl — invisible plane on the bed surface that captures
 * pointer events when mouse-control mode is active.
 *
 * Clicking/dragging on the bed sets the actuator target XY position.
 * Z is left unchanged.
 */

import { useRef } from "react";
import type { Mesh } from "three";
import * as THREE from "three";
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
  const draggingRef = useRef(false);

  const width = bed.x_max - bed.x_min;
  const depth = bed.y_max - bed.y_min;
  const cx = bed.x_min + width / 2;
  const cz = bed.y_min + depth / 2;
  // Make capture plane 3x bed size so fast drags never escape
  const planeW = width * 3;
  const planeD = depth * 3;

  if (!enabled) return null;

  function handlePointer(e: any) {
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

  return (
    <mesh
      ref={planeRef}
      position={[cx, 0.5, cz]}
      rotation={[-Math.PI / 2, 0, 0]}
      onPointerDown={(e) => {
        e.stopPropagation();
        draggingRef.current = true;
        (e.target as any).setPointerCapture?.(e.pointerId);
        handlePointer(e);
      }}
      onPointerMove={(e) => {
        if (draggingRef.current) handlePointer(e);
      }}
      onPointerUp={(e) => {
        e.stopPropagation();
        draggingRef.current = false;
        (e.target as any).releasePointerCapture?.(e.pointerId);
        // Allow reconciliation after a short delay
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
  );
}
