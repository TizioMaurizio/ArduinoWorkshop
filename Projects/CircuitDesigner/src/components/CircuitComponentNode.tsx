import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { getComponentByType } from '../data/components';
import type { CircuitNode } from '../store/circuitStore';

function CircuitComponentNode({ data, selected }: NodeProps<CircuitNode>) {
  const def = getComponentByType(data.componentType);
  if (!def) return null;

  const nodeColor = (data.properties.nodeColor as string) || def.color;
  const leftPins = def.pins.filter((p) => p.position === 'left').sort((a, b) => a.index - b.index);
  const rightPins = def.pins.filter((p) => p.position === 'right').sort((a, b) => a.index - b.index);

  const pinSpacing = 24;
  const headerHeight = 32;
  const minHeight = Math.max(
    leftPins.length * pinSpacing + headerHeight + 8,
    rightPins.length * pinSpacing + headerHeight + 8,
    60
  );

  return (
    <div
      style={{
        background: '#1e1e2e',
        border: `2px solid ${selected ? '#f5c542' : nodeColor}`,
        borderRadius: 8,
        minWidth: 140,
        minHeight,
        padding: 0,
        boxShadow: selected ? '0 0 12px rgba(245,197,66,0.4)' : '0 2px 8px rgba(0,0,0,0.3)',
        transition: 'border-color 0.2s, box-shadow 0.2s',
      }}
    >
      {/* Header */}
      <div
        style={{
          background: nodeColor,
          color: '#fff',
          padding: '4px 10px',
          borderRadius: '6px 6px 0 0',
          fontSize: 11,
          fontWeight: 600,
          textAlign: 'center',
          textShadow: '0 1px 2px rgba(0,0,0,0.3)',
        }}
      >
        {data.label}
      </div>

      {/* Pins */}
      <div style={{ position: 'relative', padding: '4px 0' }}>
        {/* Left pins */}
        {leftPins.map((pin) => (
          <div key={pin.id} style={{ position: 'relative', height: pinSpacing }}>
            <Handle
              type="target"
              position={Position.Left}
              id={pin.id}
              style={{
                top: '50%',
                background: getPinColor(pin.type),
                width: 10,
                height: 10,
                border: '2px solid #333',
              }}
            />
            <Handle
              type="source"
              position={Position.Left}
              id={pin.id}
              style={{
                top: '50%',
                background: 'transparent',
                width: 10,
                height: 10,
                border: 'none',
                pointerEvents: 'none',
              }}
            />
            <span
              style={{
                position: 'absolute',
                left: 16,
                top: '50%',
                transform: 'translateY(-50%)',
                fontSize: 9,
                color: '#ccc',
                whiteSpace: 'nowrap',
              }}
            >
              {pin.label}
            </span>
          </div>
        ))}

        {/* Right pins */}
        {rightPins.map((pin, idx) => (
          <div
            key={pin.id}
            style={{
              position: 'absolute',
              right: 0,
              top: idx * pinSpacing + 4,
              height: pinSpacing,
              width: '50%',
            }}
          >
            <Handle
              type="source"
              position={Position.Right}
              id={pin.id}
              style={{
                top: '50%',
                background: getPinColor(pin.type),
                width: 10,
                height: 10,
                border: '2px solid #333',
              }}
            />
            <Handle
              type="target"
              position={Position.Right}
              id={pin.id}
              style={{
                top: '50%',
                background: 'transparent',
                width: 10,
                height: 10,
                border: 'none',
                pointerEvents: 'none',
              }}
            />
            <span
              style={{
                position: 'absolute',
                right: 16,
                top: '50%',
                transform: 'translateY(-50%)',
                fontSize: 9,
                color: '#ccc',
                whiteSpace: 'nowrap',
                textAlign: 'right',
              }}
            >
              {pin.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function getPinColor(type: string): string {
  switch (type) {
    case 'power': return '#ff5252';
    case 'ground': return '#333333';
    case 'digital': return '#4caf50';
    case 'analog': return '#ff9800';
    case 'pwm': return '#9c27b0';
    case 'i2c': return '#2196f3';
    case 'spi': return '#00bcd4';
    case 'uart': return '#ffeb3b';
    default: return '#9e9e9e';
  }
}

export default memo(CircuitComponentNode);
