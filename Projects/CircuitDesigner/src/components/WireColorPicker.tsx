import { useCircuitStore } from '../store/circuitStore';

const WIRE_COLORS = [
  { label: 'Red', value: '#ef5350' },
  { label: 'Orange', value: '#ffa726' },
  { label: 'Yellow', value: '#ffee58' },
  { label: 'Green', value: '#66bb6a' },
  { label: 'Blue', value: '#42a5f5' },
  { label: 'Purple', value: '#ab47bc' },
  { label: 'White', value: '#eeeeee' },
  { label: 'Black', value: '#444444' },
  { label: 'Gray', value: '#888888' },
];

export default function WireColorPicker() {
  const { edges, selectedEdgeId, setEdgeColor, setSelectedEdge } = useCircuitStore();
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);

  if (!selectedEdge) return null;

  const currentColor = (selectedEdge.style?.stroke as string) ?? '#666';
  const sourceHandle = selectedEdge.sourceHandle ?? '?';
  const targetHandle = selectedEdge.targetHandle ?? '?';

  return (
    <div style={styles.overlay}>
      <div style={styles.panel}>
        <div style={styles.header}>
          <span style={styles.title}>Wire Color</span>
          <button onClick={() => setSelectedEdge(null)} style={styles.closeBtn}>✕</button>
        </div>
        <div style={styles.info}>
          <span style={styles.label}>{sourceHandle}</span>
          <span style={{ ...styles.wireSample, background: currentColor }} />
          <span style={styles.label}>{targetHandle}</span>
        </div>
        <div style={styles.colors}>
          {WIRE_COLORS.map((c) => (
            <button
              key={c.value}
              title={c.label}
              onClick={() => setEdgeColor(selectedEdge.id, c.value)}
              style={{
                ...styles.swatch,
                background: c.value,
                outline: currentColor === c.value ? '2px solid #fff' : '2px solid transparent',
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'absolute',
    bottom: 50,
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 100,
    pointerEvents: 'auto',
  },
  panel: {
    background: '#1e1e2e',
    border: '1px solid #444',
    borderRadius: 8,
    padding: '10px 14px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
    minWidth: 200,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  title: {
    color: '#e0e0e0',
    fontSize: 12,
    fontWeight: 600,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#888',
    fontSize: 14,
    cursor: 'pointer',
    padding: '0 2px',
  },
  info: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
    justifyContent: 'center',
  },
  label: {
    color: '#aaa',
    fontSize: 10,
    textTransform: 'uppercase',
  },
  wireSample: {
    width: 40,
    height: 3,
    borderRadius: 2,
  },
  colors: {
    display: 'flex',
    gap: 6,
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  swatch: {
    width: 24,
    height: 24,
    borderRadius: '50%',
    border: 'none',
    cursor: 'pointer',
    transition: 'transform 0.15s, outline 0.15s',
  },
};
