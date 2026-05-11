import { useCallback } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import ComponentPalette from './components/ComponentPalette';
import CircuitCanvas from './components/CircuitCanvas';
import PropertiesPanel from './components/PropertiesPanel';
import ValidationPanel from './components/ValidationPanel';
import WireColorPicker from './components/WireColorPicker';
import CodeSimulator from './components/CodeSimulator';
import Toolbar from './components/Toolbar';
import { useCircuitStore } from './store/circuitStore';

export default function App() {
  const addComponent = useCircuitStore((s) => s.addComponent);

  const handleAddFromPalette = useCallback(
    (componentType: string) => {
      // Add at a semi-random position in the center area
      const x = 300 + Math.random() * 200;
      const y = 100 + Math.random() * 200;
      addComponent(componentType, { x, y });
    },
    [addComponent]
  );

  return (
    <ReactFlowProvider>
      <div style={styles.app}>
        <Toolbar />
        <div style={styles.main}>
          <ComponentPalette onAddComponent={handleAddFromPalette} />
          <div style={styles.canvasArea}>
            <div style={styles.canvasWrapper}>
              <CircuitCanvas />
              <WireColorPicker />
            </div>
            <CodeSimulator />
            <ValidationPanel />
          </div>
          <PropertiesPanel />
        </div>
      </div>
    </ReactFlowProvider>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    width: '100vw',
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  main: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
  },
  canvasArea: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  canvasWrapper: {
    flex: 1,
    position: 'relative',
    display: 'flex',
    overflow: 'hidden',
  },
};
