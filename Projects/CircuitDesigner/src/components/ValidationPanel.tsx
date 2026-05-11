import { useCircuitStore } from '../store/circuitStore';

export default function ValidationPanel() {
  const { validationMessages, validateCircuit } = useCircuitStore();

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.title}>Validation</span>
        <button onClick={validateCircuit} style={styles.btn}>
          Run Check
        </button>
      </div>
      <div style={styles.messages}>
        {validationMessages.length === 0 ? (
          <p style={styles.empty}>Click "Run Check" to validate your circuit</p>
        ) : (
          validationMessages.map((msg, i) => (
            <div key={i} style={{ ...styles.message, borderLeftColor: getSeverityColor(msg.severity) }}>
              <span style={{ ...styles.icon, color: getSeverityColor(msg.severity) }}>
                {getSeverityIcon(msg.severity)}
              </span>
              <span style={styles.text}>{msg.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'error': return '#ef5350';
    case 'warning': return '#ffa726';
    case 'info': return '#42a5f5';
    default: return '#888';
  }
}

function getSeverityIcon(severity: string): string {
  switch (severity) {
    case 'error': return '✕';
    case 'warning': return '⚠';
    case 'info': return 'ℹ';
    default: return '•';
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: '#1a1a2e',
    borderTop: '1px solid #333',
    maxHeight: 180,
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 16px',
    borderBottom: '1px solid #2a2a3e',
  },
  title: {
    color: '#e0e0e0',
    fontSize: 12,
    fontWeight: 600,
  },
  btn: {
    padding: '4px 12px',
    border: 'none',
    borderRadius: 4,
    background: '#2979ff',
    color: '#fff',
    fontSize: 11,
    cursor: 'pointer',
    fontWeight: 500,
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '4px 12px',
  },
  empty: {
    color: '#888',
    fontSize: 11,
    textAlign: 'center',
    padding: '12px 0',
  },
  message: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 8,
    padding: '6px 8px',
    borderLeft: '3px solid',
    marginBottom: 4,
    borderRadius: '0 4px 4px 0',
    background: '#2a2a3e',
  },
  icon: {
    fontSize: 12,
    fontWeight: 700,
    flexShrink: 0,
    marginTop: 1,
  },
  text: {
    color: '#ddd',
    fontSize: 11,
    lineHeight: 1.4,
  },
};
