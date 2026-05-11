import { useState, useRef, useCallback, useEffect } from 'react';
import { useCircuitStore } from '../store/circuitStore';

interface SimLine {
  text: string;
  type: 'setup' | 'loop' | 'comment' | 'blank';
}

interface SimState {
  running: boolean;
  currentLine: number;
  pinStates: Record<string, boolean>;
  servoAngle: number;
  serialOutput: string[];
  loopCount: number;
}

function parseSketch(code: string): SimLine[] {
  return code.split('\n').map((text) => {
    const trimmed = text.trim();
    if (!trimmed) return { text, type: 'blank' };
    if (trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*'))
      return { text, type: 'comment' };
    return { text, type: 'loop' };
  });
}

function extractActions(line: string) {
  const actions: Array<{ type: string; args: string[] }> = [];
  const dw = line.match(/digitalWrite\(\s*(\w+)\s*,\s*(\w+)\s*\)/);
  if (dw) actions.push({ type: 'digitalWrite', args: [dw[1], dw[2]] });
  const pm = line.match(/pinMode\(\s*(\w+)\s*,\s*(\w+)\s*\)/);
  if (pm) actions.push({ type: 'pinMode', args: [pm[1], pm[2]] });
  const sp = line.match(/Serial\.println\(\s*"([^"]*)"\s*\)/);
  if (sp) actions.push({ type: 'serialPrintln', args: [sp[1]] });
  const sb = line.match(/Serial\.begin\(\s*(\d+)\s*\)/);
  if (sb) actions.push({ type: 'serialBegin', args: [sb[1]] });
  const dl = line.match(/delay\(\s*(\w+)\s*\)/);
  if (dl) actions.push({ type: 'delay', args: [dl[1]] });
  const sw = line.match(/\.write\(\s*(\w+)\s*\)/);
  if (sw) actions.push({ type: 'servoWrite', args: [sw[1]] });
  const sa = line.match(/\.attach\(\s*(\w+)\s*\)/);
  if (sa) actions.push({ type: 'servoAttach', args: [sa[1]] });
  return actions;
}

function resolveConstants(code: string): Record<string, string> {
  const consts: Record<string, string> = {};
  const re = /(?:const\s+\w+\s+|#define\s+)(\w+)\s+(\S+)/g;
  let m;
  while ((m = re.exec(code)) !== null) {
    consts[m[1]] = m[2].replace(/;$/, '');
  }
  return consts;
}

export default function CodeSimulator() {
  const { code, setCode } = useCircuitStore();
  const [sim, setSim] = useState<SimState>({
    running: false,
    currentLine: -1,
    pinStates: {},
    servoAngle: 90,
    serialOutput: [],
    loopCount: 0,
  });
  const [collapsed, setCollapsed] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const simRef = useRef(sim);
  simRef.current = sim;

  const lines = parseSketch(code);
  const consts = resolveConstants(code);

  const stop = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    setSim((s) => ({ ...s, running: false, currentLine: -1 }));
  }, []);

  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  const resolveValue = useCallback(
    (v: string) => consts[v] ?? v,
    [consts]
  );

  const stepLine = useCallback(
    (lineIdx: number, loopStart: number, loopEnd: number) => {
      const line = lines[lineIdx];
      if (!line) {
        stop();
        return;
      }

      setSim((s) => ({ ...s, currentLine: lineIdx }));

      const actions = extractActions(line.text);
      let delayMs = 150; // default step speed

      for (const action of actions) {
        if (action.type === 'digitalWrite') {
          const pin = resolveValue(action.args[0]);
          const val = action.args[1] === 'HIGH';
          setSim((s) => ({
            ...s,
            pinStates: { ...s.pinStates, [pin]: val },
          }));
        }
        if (action.type === 'serialPrintln') {
          setSim((s) => ({
            ...s,
            serialOutput: [...s.serialOutput.slice(-19), action.args[0]],
          }));
        }
        if (action.type === 'delay') {
          const ms = parseInt(resolveValue(action.args[0]), 10);
          delayMs = Math.min(ms, 1500); // cap visual delay
        }
        if (action.type === 'servoWrite') {
          const angle = Math.max(0, Math.min(180, parseInt(resolveValue(action.args[0]), 10)));
          if (!isNaN(angle)) setSim((s) => ({ ...s, servoAngle: angle }));
        }
      }

      // Advance to next line
      let next = lineIdx + 1;
      if (next > loopEnd) {
        next = loopStart;
        setSim((s) => ({ ...s, loopCount: s.loopCount + 1 }));
        if (simRef.current.loopCount >= 20) {
          stop();
          return;
        }
      }

      timerRef.current = setTimeout(() => {
        if (simRef.current.running) stepLine(next, loopStart, loopEnd);
      }, delayMs);
    },
    [lines, resolveValue, stop]
  );

  const start = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    // Find setup() and loop() regions
    let setupStart = -1, loopStart = -1, loopEnd = -1;
    let braceDepth = 0;
    let inSetup = false, inLoop = false;
    for (let i = 0; i < lines.length; i++) {
      const t = lines[i].text.trim();
      if (t.match(/void\s+setup\s*\(/)) { setupStart = i + 1; inSetup = true; braceDepth = 0; }
      if (t.match(/void\s+loop\s*\(/)) { loopStart = i + 1; inLoop = true; braceDepth = 0; }
      for (const ch of t) {
        if (ch === '{') braceDepth++;
        if (ch === '}') {
          braceDepth--;
          if (braceDepth <= 0) {
            if (inSetup) { inSetup = false; }
            if (inLoop) { loopEnd = i - 1; inLoop = false; }
          }
        }
      }
    }
    if (setupStart < 0) setupStart = 0;
    if (loopStart < 0) loopStart = 0;
    if (loopEnd < loopStart) loopEnd = lines.length - 1;

    setSim({
      running: true,
      currentLine: setupStart,
      pinStates: {},
      servoAngle: 90,
      serialOutput: [],
      loopCount: 0,
    });

    // Run setup lines first, then loop
    const runSetup = (idx: number) => {
      if (idx >= loopStart) {
        // Setup done, start loop
        stepLine(loopStart, loopStart, loopEnd);
        return;
      }
      setSim((s) => ({ ...s, currentLine: idx }));
      const actions = extractActions(lines[idx].text);
      for (const a of actions) {
        if (a.type === 'serialPrintln') {
          setSim((s) => ({
            ...s,
            serialOutput: [...s.serialOutput.slice(-19), a.args[0]],
          }));
        }
        if (a.type === 'servoWrite') {
          const angle = Math.max(0, Math.min(180, parseInt(resolveValue(a.args[0]), 10)));
          if (!isNaN(angle)) setSim((s) => ({ ...s, servoAngle: angle }));
        }
      }
      timerRef.current = setTimeout(() => {
        if (simRef.current.running) runSetup(idx + 1);
      }, 100);
    };
    runSetup(setupStart);
  }, [lines, stepLine]);

  const ledPin = resolveValue('LED_PIN') || '13';
  const ledOn = sim.pinStates[ledPin] ?? false;
  const hasServo = /Servo|\.write\(|\.attach\(/i.test(code);
  const hasLed = /LED_PIN|digitalWrite/i.test(code);

  if (collapsed) {
    return (
      <div style={styles.collapsedBar}>
        <button onClick={() => setCollapsed(false)} style={styles.expandBtn}>
          ▶ Code &amp; Simulator
        </button>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.title}>Code &amp; Simulator</span>
        <div style={styles.headerButtons}>
          {!sim.running ? (
            <button onClick={start} style={styles.runBtn} disabled={!code.trim()}>
              ▶ Run
            </button>
          ) : (
            <button onClick={stop} style={styles.stopBtn}>
              ■ Stop
            </button>
          )}
          <button onClick={() => setCollapsed(true)} style={styles.collapseBtn}>
            ▼
          </button>
        </div>
      </div>

      <div style={styles.body}>
        {/* Code editor */}
        <div style={styles.codeSection}>
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            style={styles.codeArea}
            spellCheck={false}
            placeholder="// Paste or write Arduino code here..."
          />
          {/* Line highlight overlay */}
          {sim.running && sim.currentLine >= 0 && (
            <div style={styles.lineOverlay}>
              {lines.map((_, i) => (
                <div
                  key={i}
                  style={{
                    height: 18,
                    background: i === sim.currentLine ? 'rgba(245,197,66,0.25)' : 'transparent',
                    borderLeft: i === sim.currentLine ? '3px solid #f5c542' : '3px solid transparent',
                    transition: 'background 0.15s',
                  }}
                />
              ))}
            </div>
          )}
        </div>

        {/* Simulator output */}
        <div style={styles.simSection}>
          {/* LED indicator */}
          {hasLed && !hasServo && (
            <div style={styles.ledBox}>
              <div style={styles.ledLabel}>Pin {ledPin}</div>
              <div
                style={{
                  ...styles.ledIndicator,
                  background: ledOn ? '#ff1744' : '#4a1a1a',
                  boxShadow: ledOn ? '0 0 20px #ff1744, 0 0 40px rgba(255,23,68,0.4)' : 'none',
                }}
              />
              <div style={styles.ledState}>{ledOn ? 'HIGH' : 'LOW'}</div>
            </div>
          )}

          {/* Servo gauge */}
          {hasServo && (
            <div style={styles.servoBox}>
              <div style={styles.servoLabel}>Servo</div>
              <svg width={120} height={72} viewBox="0 0 120 72" style={{ display: 'block', margin: '0 auto' }}>
                {/* Background arc */}
                <path
                  d="M 10 65 A 50 50 0 0 1 110 65"
                  fill="none"
                  stroke="#2a2a3e"
                  strokeWidth={8}
                  strokeLinecap="round"
                />
                {/* Active arc from 90° to current angle */}
                {sim.servoAngle !== 90 && (() => {
                  const startDeg = Math.min(90, sim.servoAngle);
                  const endDeg = Math.max(90, sim.servoAngle);
                  const cx = 60, cy = 65, r = 50;
                  const sa = Math.PI - (endDeg * Math.PI) / 180;
                  const ea = Math.PI - (startDeg * Math.PI) / 180;
                  const x1 = cx + r * Math.cos(sa);
                  const y1 = cy - r * Math.sin(sa);
                  const x2 = cx + r * Math.cos(ea);
                  const y2 = cy - r * Math.sin(ea);
                  const large = (endDeg - startDeg) > 180 ? 1 : 0;
                  return (
                    <path
                      d={`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`}
                      fill="none"
                      stroke="#42a5f5"
                      strokeWidth={8}
                      strokeLinecap="round"
                      opacity={0.6}
                    />
                  );
                })()}
                {/* Tick marks */}
                {[0, 45, 90, 135, 180].map((deg) => {
                  const rad = Math.PI - (deg * Math.PI) / 180;
                  const cx = 60, cy = 65, r1 = 44, r2 = 50;
                  return (
                    <line
                      key={deg}
                      x1={cx + r1 * Math.cos(rad)}
                      y1={cy - r1 * Math.sin(rad)}
                      x2={cx + r2 * Math.cos(rad)}
                      y2={cy - r2 * Math.sin(rad)}
                      stroke="#666"
                      strokeWidth={1.5}
                    />
                  );
                })}
                {/* Labels */}
                <text x={6} y={70} fill="#888" fontSize={8} textAnchor="middle">0°</text>
                <text x={60} y={10} fill="#888" fontSize={8} textAnchor="middle">90°</text>
                <text x={114} y={70} fill="#888" fontSize={8} textAnchor="middle">180°</text>
                {/* Needle */}
                {(() => {
                  const rad = Math.PI - (sim.servoAngle * Math.PI) / 180;
                  const cx = 60, cy = 65, len = 42;
                  const nx = cx + len * Math.cos(rad);
                  const ny = cy - len * Math.sin(rad);
                  return (
                    <line
                      x1={cx}
                      y1={cy}
                      x2={nx}
                      y2={ny}
                      stroke="#ffb74d"
                      strokeWidth={2.5}
                      strokeLinecap="round"
                      style={{ transition: 'x2 0.3s, y2 0.3s' }}
                    />
                  );
                })()}
                {/* Center dot */}
                <circle cx={60} cy={65} r={4} fill="#ffb74d" />
              </svg>
              <div style={styles.servoAngleText}>{sim.servoAngle}°</div>
            </div>
          )}

          {/* Serial monitor */}
          <div style={styles.serialBox}>
            <div style={styles.serialTitle}>Serial Monitor</div>
            <div style={styles.serialOutput}>
              {sim.serialOutput.length === 0 ? (
                <span style={styles.serialHint}>No output yet</span>
              ) : (
                sim.serialOutput.map((line, i) => (
                  <div key={i} style={styles.serialLine}>{line}</div>
                ))
              )}
            </div>
          </div>

          {sim.running && (
            <div style={styles.loopCounter}>Loop #{sim.loopCount + 1}</div>
          )}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    borderTop: '1px solid #333',
    background: '#12121f',
    maxHeight: 320,
    minHeight: 200,
  },
  collapsedBar: {
    borderTop: '1px solid #333',
    background: '#12121f',
    padding: '4px 12px',
  },
  expandBtn: {
    background: 'none',
    border: 'none',
    color: '#aaa',
    fontSize: 11,
    cursor: 'pointer',
    padding: '4px 8px',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '6px 12px',
    borderBottom: '1px solid #2a2a3e',
  },
  title: {
    color: '#e0e0e0',
    fontSize: 12,
    fontWeight: 600,
  },
  headerButtons: {
    display: 'flex',
    gap: 6,
  },
  runBtn: {
    background: '#2e7d32',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    padding: '4px 12px',
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
  },
  stopBtn: {
    background: '#c62828',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    padding: '4px 12px',
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
  },
  collapseBtn: {
    background: 'none',
    border: 'none',
    color: '#888',
    fontSize: 12,
    cursor: 'pointer',
    padding: '0 4px',
  },
  body: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
  codeSection: {
    flex: 2,
    position: 'relative',
    overflow: 'hidden',
  },
  codeArea: {
    width: '100%',
    height: '100%',
    resize: 'none',
    background: '#0d0d1a',
    color: '#c5e1a5',
    border: 'none',
    padding: '8px 12px',
    fontFamily: '"Cascadia Code", "Fira Code", "Consolas", monospace',
    fontSize: 12,
    lineHeight: '18px',
    outline: 'none',
    tabSize: 2,
  },
  lineOverlay: {
    position: 'absolute',
    top: 8,
    left: 0,
    right: 0,
    pointerEvents: 'none',
  },
  simSection: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    borderLeft: '1px solid #2a2a3e',
    padding: 10,
    gap: 8,
    minWidth: 160,
  },
  ledBox: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 10px',
    background: '#1a1a2e',
    borderRadius: 6,
  },
  ledLabel: {
    color: '#aaa',
    fontSize: 10,
    textTransform: 'uppercase',
    minWidth: 40,
  },
  ledIndicator: {
    width: 24,
    height: 24,
    borderRadius: '50%',
    border: '2px solid #555',
    transition: 'background 0.2s, box-shadow 0.2s',
  },
  ledState: {
    color: '#e0e0e0',
    fontSize: 11,
    fontWeight: 600,
    fontFamily: 'monospace',
  },
  serialBox: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    background: '#0a0a14',
    borderRadius: 4,
    overflow: 'hidden',
  },
  serialTitle: {
    color: '#888',
    fontSize: 9,
    textTransform: 'uppercase',
    padding: '4px 8px',
    borderBottom: '1px solid #222',
    letterSpacing: 0.5,
  },
  serialOutput: {
    flex: 1,
    overflowY: 'auto',
    padding: '4px 8px',
    fontFamily: 'monospace',
    fontSize: 11,
  },
  serialHint: {
    color: '#555',
    fontSize: 10,
  },
  serialLine: {
    color: '#81c784',
    lineHeight: 1.6,
  },
  loopCounter: {
    color: '#666',
    fontSize: 10,
    textAlign: 'center',
  },
  servoBox: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '8px 10px',
    background: '#1a1a2e',
    borderRadius: 6,
    gap: 2,
  },
  servoLabel: {
    color: '#aaa',
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  servoAngleText: {
    color: '#ffb74d',
    fontSize: 16,
    fontWeight: 700,
    fontFamily: 'monospace',
  },
};
