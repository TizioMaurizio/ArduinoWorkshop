import { useRef, useCallback } from 'react';
import { useCircuitStore } from '../store/circuitStore';

export default function Toolbar() {
  const { circuitName, setCircuitName, clearCircuit, exportCircuit, importCircuit, nodes, edges } =
    useCircuitStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleExport = useCallback(() => {
    const json = exportCircuit();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${circuitName.replace(/\s+/g, '_')}.circuit.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [exportCircuit, circuitName]);

  const handleImport = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        const text = ev.target?.result;
        if (typeof text === 'string') {
          importCircuit(text);
        }
      };
      reader.readAsText(file);
      e.target.value = '';
    },
    [importCircuit]
  );

  return (
    <div style={styles.toolbar}>
      <div style={styles.left}>
        <span style={styles.logo}>⚡</span>
        <input
          type="text"
          value={circuitName}
          onChange={(e) => setCircuitName(e.target.value)}
          style={styles.nameInput}
        />
      </div>

      <div style={styles.center}>
        <span style={styles.stat}>{nodes.length} components</span>
        <span style={styles.divider}>|</span>
        <span style={styles.stat}>{edges.length} wires</span>
      </div>

      <div style={styles.right}>
        <button onClick={handleImport} style={styles.btn}>
          Import
        </button>
        <button onClick={handleExport} style={styles.btn}>
          Export
        </button>
        <button onClick={clearCircuit} style={{ ...styles.btn, ...styles.dangerBtn }}>
          Clear
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json,.circuit.json"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 16px',
    background: '#16162a',
    borderBottom: '1px solid #333',
    height: 48,
  },
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  logo: {
    fontSize: 20,
  },
  nameInput: {
    background: 'transparent',
    border: '1px solid transparent',
    color: '#e0e0e0',
    fontSize: 14,
    fontWeight: 600,
    padding: '4px 8px',
    borderRadius: 4,
    outline: 'none',
    width: 200,
    transition: 'border-color 0.2s',
  },
  center: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  stat: {
    color: '#888',
    fontSize: 12,
  },
  divider: {
    color: '#444',
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  btn: {
    padding: '6px 14px',
    border: 'none',
    borderRadius: 4,
    background: '#2a2a3e',
    color: '#e0e0e0',
    fontSize: 12,
    cursor: 'pointer',
    fontWeight: 500,
    transition: 'background 0.15s',
  },
  dangerBtn: {
    background: '#4a1a1a',
    color: '#ff8a80',
  },
};
