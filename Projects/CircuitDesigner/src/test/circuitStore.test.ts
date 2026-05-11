import { describe, it, expect, beforeEach } from 'vitest';
import { useCircuitStore } from '../store/circuitStore';

describe('circuitStore', () => {
  beforeEach(() => {
    useCircuitStore.getState().clearCircuit();
  });

  describe('addComponent', () => {
    it('adds a valid component to the canvas', () => {
      const store = useCircuitStore.getState();
      store.addComponent('arduino-uno', { x: 100, y: 200 });

      const { nodes } = useCircuitStore.getState();
      expect(nodes).toHaveLength(1);
      expect(nodes[0].data.componentType).toBe('arduino-uno');
      expect(nodes[0].data.label).toBe('Arduino Uno');
      expect(nodes[0].position).toEqual({ x: 100, y: 200 });
    });

    it('does not add an unknown component type', () => {
      const store = useCircuitStore.getState();
      store.addComponent('nonexistent-component', { x: 0, y: 0 });

      const { nodes } = useCircuitStore.getState();
      expect(nodes).toHaveLength(0);
    });

    it('adds multiple components with unique IDs', () => {
      const store = useCircuitStore.getState();
      store.addComponent('led', { x: 0, y: 0 });
      store.addComponent('led', { x: 100, y: 0 });

      const { nodes } = useCircuitStore.getState();
      expect(nodes).toHaveLength(2);
      expect(nodes[0].id).not.toBe(nodes[1].id);
    });
  });

  describe('removeComponent', () => {
    it('removes a component and its connected edges', () => {
      const store = useCircuitStore.getState();
      store.addComponent('arduino-uno', { x: 0, y: 0 });
      store.addComponent('led', { x: 200, y: 0 });

      const { nodes } = useCircuitStore.getState();
      const arduinoId = nodes[0].id;
      const ledId = nodes[1].id;

      // Simulate adding an edge
      useCircuitStore.setState({
        edges: [{ id: 'e1', source: arduinoId, target: ledId, sourceHandle: 'd13', targetHandle: 'anode' }],
      });

      store.removeComponent(ledId);

      const state = useCircuitStore.getState();
      expect(state.nodes).toHaveLength(1);
      expect(state.nodes[0].id).toBe(arduinoId);
      expect(state.edges).toHaveLength(0);
    });

    it('clears selection when removing the selected node', () => {
      const store = useCircuitStore.getState();
      store.addComponent('resistor', { x: 0, y: 0 });

      const nodeId = useCircuitStore.getState().nodes[0].id;
      store.setSelectedNode(nodeId);
      expect(useCircuitStore.getState().selectedNodeId).toBe(nodeId);

      store.removeComponent(nodeId);
      expect(useCircuitStore.getState().selectedNodeId).toBeNull();
    });
  });

  describe('setSelectedNode', () => {
    it('sets and clears the selected node', () => {
      const store = useCircuitStore.getState();
      store.addComponent('esp32', { x: 0, y: 0 });
      const nodeId = useCircuitStore.getState().nodes[0].id;

      store.setSelectedNode(nodeId);
      expect(useCircuitStore.getState().selectedNodeId).toBe(nodeId);

      store.setSelectedNode(null);
      expect(useCircuitStore.getState().selectedNodeId).toBeNull();
    });
  });

  describe('updateNodeProperty', () => {
    it('updates a property on a specific node', () => {
      const store = useCircuitStore.getState();
      store.addComponent('resistor', { x: 0, y: 0 });
      const nodeId = useCircuitStore.getState().nodes[0].id;

      store.updateNodeProperty(nodeId, 'resistance', 470);
      const node = useCircuitStore.getState().nodes[0];
      expect(node.data.properties.resistance).toBe(470);
    });
  });

  describe('circuitName', () => {
    it('has a default name', () => {
      expect(useCircuitStore.getState().circuitName).toBe('Untitled Circuit');
    });

    it('allows renaming', () => {
      useCircuitStore.getState().setCircuitName('My LED Circuit');
      expect(useCircuitStore.getState().circuitName).toBe('My LED Circuit');
    });
  });

  describe('clearCircuit', () => {
    it('removes all nodes, edges, and resets state', () => {
      const store = useCircuitStore.getState();
      store.addComponent('arduino-uno', { x: 0, y: 0 });
      store.addComponent('led', { x: 100, y: 0 });
      store.setSelectedNode(useCircuitStore.getState().nodes[0].id);

      store.clearCircuit();
      const state = useCircuitStore.getState();
      expect(state.nodes).toHaveLength(0);
      expect(state.edges).toHaveLength(0);
      expect(state.selectedNodeId).toBeNull();
      expect(state.validationMessages).toHaveLength(0);
    });
  });

  describe('exportCircuit / importCircuit', () => {
    it('round-trips a circuit through JSON', () => {
      const store = useCircuitStore.getState();
      store.setCircuitName('Test Circuit');
      store.addComponent('arduino-uno', { x: 50, y: 50 });
      store.addComponent('servo-sg90', { x: 300, y: 50 });

      const json = store.exportCircuit();
      const parsed = JSON.parse(json);
      expect(parsed.name).toBe('Test Circuit');
      expect(parsed.nodes).toHaveLength(2);

      store.clearCircuit();
      expect(useCircuitStore.getState().nodes).toHaveLength(0);

      store.importCircuit(json);
      const state = useCircuitStore.getState();
      expect(state.nodes).toHaveLength(2);
      expect(state.circuitName).toBe('Test Circuit');
    });

    it('ignores invalid JSON on import', () => {
      const store = useCircuitStore.getState();
      store.addComponent('led', { x: 0, y: 0 });

      store.importCircuit('not valid json{{{');
      // Should not crash, state unchanged
      expect(useCircuitStore.getState().nodes).toHaveLength(1);
    });
  });

  describe('validateCircuit', () => {
    it('warns about disconnected components', () => {
      const store = useCircuitStore.getState();
      store.addComponent('led', { x: 0, y: 0 });
      store.addComponent('resistor', { x: 100, y: 0 });

      store.validateCircuit();
      const messages = useCircuitStore.getState().validationMessages;
      const warnings = messages.filter((m) => m.severity === 'warning');
      expect(warnings.length).toBeGreaterThanOrEqual(2);
    });

    it('suggests adding a microcontroller when none present', () => {
      const store = useCircuitStore.getState();
      store.addComponent('led', { x: 0, y: 0 });

      store.validateCircuit();
      const messages = useCircuitStore.getState().validationMessages;
      const info = messages.find((m) => m.message.includes('microcontroller'));
      expect(info).toBeDefined();
    });

    it('passes validation for an empty circuit (no messages)', () => {
      useCircuitStore.getState().validateCircuit();
      expect(useCircuitStore.getState().validationMessages).toHaveLength(0);
    });

    it('detects missing ground connections', () => {
      const store = useCircuitStore.getState();
      store.addComponent('arduino-uno', { x: 0, y: 0 });
      store.addComponent('dht11', { x: 300, y: 0 });

      const { nodes } = useCircuitStore.getState();
      const arduinoId = nodes[0].id;
      const dhtId = nodes[1].id;

      // Connect data pin only (no ground)
      useCircuitStore.setState({
        edges: [
          { id: 'e1', source: arduinoId, target: dhtId, sourceHandle: 'd2', targetHandle: 'data' },
        ],
      });

      store.validateCircuit();
      const messages = useCircuitStore.getState().validationMessages;
      const groundErrors = messages.filter((m) => m.message.includes('ground'));
      expect(groundErrors.length).toBeGreaterThan(0);
    });
  });
});
