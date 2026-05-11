import { useCircuitStore } from '../store/circuitStore';
import { getComponentByType } from '../data/components';

const COMPONENT_COLORS = [
  { label: 'Red', value: '#e53935' },
  { label: 'Orange', value: '#fb8c00' },
  { label: 'Yellow', value: '#fdd835' },
  { label: 'Green', value: '#43a047' },
  { label: 'Teal', value: '#00897b' },
  { label: 'Blue', value: '#1e88e5' },
  { label: 'Indigo', value: '#3949ab' },
  { label: 'Purple', value: '#8e24aa' },
  { label: 'Pink', value: '#d81b60' },
  { label: 'Brown', value: '#6d4c41' },
  { label: 'Gray', value: '#757575' },
  { label: 'Cyan', value: '#00acc1' },
];

export default function PropertiesPanel() {
  const { nodes, selectedNodeId, updateNodeProperty, removeComponent } = useCircuitStore();
  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  if (!selectedNode) {
    return (
      <div style={styles.container}>
        <h3 style={styles.title}>Properties</h3>
        <p style={styles.hint}>Select a component to view its properties</p>
      </div>
    );
  }

  const def = getComponentByType(selectedNode.data.componentType);

  return (
    <div style={styles.container}>
      <h3 style={styles.title}>Properties</h3>

      <div style={styles.section}>
        <div style={styles.header}>
          <span style={{ ...styles.dot, background: def?.color ?? '#666' }} />
          <span style={styles.compName}>{selectedNode.data.label}</span>
        </div>
        {def && <p style={styles.description}>{def.description}</p>}
      </div>

      <div style={styles.section}>
        <label style={styles.label}>Component ID</label>
        <code style={styles.code}>{selectedNode.id.slice(0, 8)}</code>
      </div>

      <div style={styles.section}>
        <label style={styles.label}>Position</label>
        <div style={styles.row}>
          <span style={styles.fieldLabel}>X:</span>
          <span style={styles.fieldValue}>{Math.round(selectedNode.position.x)}</span>
          <span style={styles.fieldLabel}>Y:</span>
          <span style={styles.fieldValue}>{Math.round(selectedNode.position.y)}</span>
        </div>
      </div>

      {def && (
        <div style={styles.section}>
          <label style={styles.label}>Pins ({def.pins.length})</label>
          <div style={styles.pinList}>
            {def.pins.map((pin) => (
              <div key={pin.id} style={styles.pinRow}>
                <span style={{ ...styles.pinDot, background: getPinColor(pin.type) }} />
                <span style={styles.pinLabel}>{pin.label}</span>
                <span style={styles.pinType}>{pin.type}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Custom properties based on component type */}
      {selectedNode.data.componentType === 'resistor' && (
        <div style={styles.section}>
          <label style={styles.label}>Resistance (Ω)</label>
          <input
            type="number"
            value={selectedNode.data.properties.resistance ?? 220}
            onChange={(e) => updateNodeProperty(selectedNode.id, 'resistance', Number(e.target.value))}
            style={styles.input}
          />
        </div>
      )}

      {selectedNode.data.componentType === 'capacitor' && (
        <div style={styles.section}>
          <label style={styles.label}>Capacitance (µF)</label>
          <input
            type="number"
            value={selectedNode.data.properties.capacitance ?? 100}
            onChange={(e) => updateNodeProperty(selectedNode.id, 'capacitance', Number(e.target.value))}
            style={styles.input}
          />
        </div>
      )}

      {selectedNode.data.componentType === 'led' && (
        <div style={styles.section}>
          <label style={styles.label}>Color</label>
          <select
            value={(selectedNode.data.properties.color as string) ?? 'red'}
            onChange={(e) => updateNodeProperty(selectedNode.id, 'color', e.target.value)}
            style={styles.input}
          >
            <option value="red">Red</option>
            <option value="green">Green</option>
            <option value="blue">Blue</option>
            <option value="yellow">Yellow</option>
            <option value="white">White</option>
          </select>
        </div>
      )}

      <div style={styles.section}>
        <label style={styles.label}>Component Color</label>
        <div style={styles.colorSwatches}>
          {COMPONENT_COLORS.map((c) => {
            const currentColor = (selectedNode.data.properties.nodeColor as string) || def?.color || '#666';
            return (
              <button
                key={c.value}
                title={c.label}
                onClick={() => updateNodeProperty(selectedNode.id, 'nodeColor', c.value)}
                style={{
                  ...styles.colorSwatch,
                  background: c.value,
                  outline: currentColor === c.value ? '2px solid #fff' : '2px solid transparent',
                }}
              />
            );
          })}
          {selectedNode.data.properties.nodeColor && (
            <button
              title="Reset to default"
              onClick={() => updateNodeProperty(selectedNode.id, 'nodeColor', '')}
              style={styles.resetColorBtn}
            >
              ↺
            </button>
          )}
        </div>
      </div>

      <div style={{ ...styles.section, marginTop: 'auto' }}>
        <button
          onClick={() => removeComponent(selectedNode.id)}
          style={styles.deleteBtn}
        >
          Delete Component
        </button>
      </div>
    </div>
  );
}

function getPinColor(type: string): string {
  switch (type) {
    case 'power': return '#ff5252';
    case 'ground': return '#333';
    case 'digital': return '#4caf50';
    case 'analog': return '#ff9800';
    case 'pwm': return '#9c27b0';
    case 'i2c': return '#2196f3';
    case 'spi': return '#00bcd4';
    case 'uart': return '#ffeb3b';
    default: return '#9e9e9e';
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: 260,
    background: '#1a1a2e',
    borderLeft: '1px solid #333',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  title: {
    margin: 0,
    padding: '12px 16px',
    fontSize: 14,
    color: '#e0e0e0',
    borderBottom: '1px solid #333',
  },
  hint: {
    color: '#888',
    fontSize: 12,
    padding: '20px 16px',
    textAlign: 'center',
  },
  section: {
    padding: '10px 16px',
    borderBottom: '1px solid #2a2a3e',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: '50%',
  },
  compName: {
    color: '#e0e0e0',
    fontSize: 13,
    fontWeight: 600,
  },
  description: {
    color: '#999',
    fontSize: 11,
    marginTop: 6,
    lineHeight: 1.4,
  },
  label: {
    display: 'block',
    color: '#aaa',
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  code: {
    color: '#7ec8e3',
    fontSize: 11,
    background: '#2a2a3e',
    padding: '2px 6px',
    borderRadius: 3,
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 12,
    color: '#ccc',
  },
  fieldLabel: {
    color: '#888',
  },
  fieldValue: {
    color: '#e0e0e0',
  },
  pinList: {
    maxHeight: 160,
    overflowY: 'auto',
  },
  pinRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '3px 0',
  },
  pinDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
  },
  pinLabel: {
    color: '#ccc',
    fontSize: 11,
  },
  pinType: {
    marginLeft: 'auto',
    color: '#888',
    fontSize: 9,
    textTransform: 'uppercase',
  },
  input: {
    width: '100%',
    padding: '5px 8px',
    borderRadius: 4,
    border: '1px solid #444',
    background: '#2a2a3e',
    color: '#e0e0e0',
    fontSize: 12,
    outline: 'none',
  },
  deleteBtn: {
    width: '100%',
    padding: '8px',
    border: 'none',
    borderRadius: 4,
    background: '#c62828',
    color: '#fff',
    fontSize: 12,
    cursor: 'pointer',
    fontWeight: 600,
  },
  colorSwatches: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 5,
  },
  colorSwatch: {
    width: 22,
    height: 22,
    borderRadius: '50%',
    border: 'none',
    cursor: 'pointer',
    padding: 0,
    outlineOffset: 2,
  },
  resetColorBtn: {
    width: 22,
    height: 22,
    borderRadius: '50%',
    border: '1px dashed #666',
    background: 'transparent',
    color: '#aaa',
    cursor: 'pointer',
    fontSize: 12,
    padding: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
};
