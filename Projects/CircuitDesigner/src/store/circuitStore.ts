import { create } from 'zustand';
import {
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  type Connection,
} from '@xyflow/react';
import { v4 as uuidv4 } from 'uuid';
import type { ValidationMessage } from '../types/circuit';
import { getComponentByType } from '../data/components';

export interface CircuitNode extends Node {
  data: {
    label: string;
    componentType: string;
    properties: Record<string, string | number>;
  };
}

interface CircuitState {
  nodes: CircuitNode[];
  edges: Edge[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  validationMessages: ValidationMessage[];
  circuitName: string;
  code: string;

  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;

  addComponent: (componentType: string, position: { x: number; y: number }) => void;
  removeComponent: (id: string) => void;
  setSelectedNode: (id: string | null) => void;
  setSelectedEdge: (id: string | null) => void;
  setEdgeColor: (edgeId: string, color: string) => void;
  updateNodeProperty: (nodeId: string, key: string, value: string | number) => void;
  validateCircuit: () => void;
  clearCircuit: () => void;
  setCircuitName: (name: string) => void;
  setCode: (code: string) => void;
  exportCircuit: () => string;
  importCircuit: (json: string) => void;
}

export const useCircuitStore = create<CircuitState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  selectedEdgeId: null,
  validationMessages: [],
  circuitName: 'Untitled Circuit',
  code: '',

  onNodesChange: (changes) => {
    set({ nodes: applyNodeChanges(changes, get().nodes) as CircuitNode[] });
  },

  onEdgesChange: (changes) => {
    set({ edges: applyEdgeChanges(changes, get().edges) });
  },

  onConnect: (connection: Connection) => {
    set({ edges: addEdge({ ...connection, type: 'smoothstep', animated: true, style: { stroke: '#b0b0b0', strokeWidth: 2 } }, get().edges) });
  },

  addComponent: (componentType, position) => {
    const def = getComponentByType(componentType);
    if (!def) return;

    const id = uuidv4();
    const newNode: CircuitNode = {
      id,
      type: 'circuitComponent',
      position,
      data: {
        label: def.label,
        componentType: def.type,
        properties: {},
      },
    };
    set({ nodes: [...get().nodes, newNode] });
  },

  removeComponent: (id) => {
    set({
      nodes: get().nodes.filter((n) => n.id !== id),
      edges: get().edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: get().selectedNodeId === id ? null : get().selectedNodeId,
    });
  },

  setSelectedNode: (id) => {
    set({ selectedNodeId: id, selectedEdgeId: null });
  },

  setSelectedEdge: (id) => {
    set({ selectedEdgeId: id, selectedNodeId: null });
  },

  setEdgeColor: (edgeId, color) => {
    set({
      edges: get().edges.map((e) =>
        e.id === edgeId
          ? { ...e, style: { ...e.style, stroke: color, strokeWidth: 2 } }
          : e
      ),
    });
  },

  updateNodeProperty: (nodeId, key, value) => {
    set({
      nodes: get().nodes.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, properties: { ...n.data.properties, [key]: value } } }
          : n
      ),
    });
  },

  validateCircuit: () => {
    const { nodes, edges } = get();
    const messages: ValidationMessage[] = [];

    // Check for disconnected components
    const connectedNodeIds = new Set<string>();
    edges.forEach((e) => {
      connectedNodeIds.add(e.source);
      connectedNodeIds.add(e.target);
    });
    nodes.forEach((n) => {
      if (!connectedNodeIds.has(n.id)) {
        messages.push({
          severity: 'warning',
          message: `${n.data.label} is not connected to anything`,
          componentIds: [n.id],
        });
      }
    });

    // Check for power connections
    const hasMCU = nodes.some((n) => {
      const def = getComponentByType(n.data.componentType);
      return def?.category === 'microcontroller';
    });
    if (nodes.length > 0 && !hasMCU) {
      messages.push({
        severity: 'info',
        message: 'No microcontroller in the circuit. Consider adding an Arduino or ESP32.',
      });
    }

    // Check for ground connections
    const groundEdges = edges.filter((e) => {
      const sourceHandle = e.sourceHandle ?? '';
      const targetHandle = e.targetHandle ?? '';
      return sourceHandle.includes('gnd') || targetHandle.includes('gnd');
    });
    const componentsNeedingGnd = nodes.filter((n) => {
      const def = getComponentByType(n.data.componentType);
      return def?.pins.some((p) => p.type === 'ground');
    });
    const groundedComponents = new Set<string>();
    groundEdges.forEach((e) => {
      groundedComponents.add(e.source);
      groundedComponents.add(e.target);
    });
    componentsNeedingGnd.forEach((n) => {
      if (!groundedComponents.has(n.id)) {
        messages.push({
          severity: 'error',
          message: `${n.data.label} is missing a ground connection`,
          componentIds: [n.id],
        });
      }
    });

    // Check for voltage mismatches on edges
    edges.forEach((e) => {
      const sourceNode = nodes.find((n) => n.id === e.source);
      const targetNode = nodes.find((n) => n.id === e.target);
      if (!sourceNode || !targetNode) return;

      const sourceDef = getComponentByType(sourceNode.data.componentType);
      const targetDef = getComponentByType(targetNode.data.componentType);
      if (!sourceDef || !targetDef) return;

      const sourcePin = sourceDef.pins.find((p) => p.id === e.sourceHandle);
      const targetPin = targetDef.pins.find((p) => p.id === e.targetHandle);

      if (sourcePin?.voltage && targetPin?.voltage && sourcePin.voltage !== targetPin.voltage) {
        messages.push({
          severity: 'error',
          message: `Voltage mismatch: ${sourceNode.data.label}.${sourcePin.label} (${sourcePin.voltage}V) → ${targetNode.data.label}.${targetPin.label} (${targetPin.voltage}V)`,
          componentIds: [sourceNode.id, targetNode.id],
          wireIds: [e.id],
        });
      }
    });

    if (messages.length === 0 && nodes.length > 0) {
      messages.push({
        severity: 'info',
        message: 'Circuit validation passed — no issues detected.',
      });
    }

    set({ validationMessages: messages });
  },

  clearCircuit: () => {
    set({ nodes: [], edges: [], selectedNodeId: null, selectedEdgeId: null, validationMessages: [], code: '' });
  },

  setCircuitName: (name) => {
    set({ circuitName: name });
  },

  setCode: (code) => {
    set({ code });
  },

  exportCircuit: () => {
    const { nodes, edges, circuitName, code } = get();
    return JSON.stringify({ name: circuitName, nodes, edges, code, exportedAt: new Date().toISOString() }, null, 2);
  },

  importCircuit: (json) => {
    try {
      const data = JSON.parse(json);
      if (data.nodes && data.edges) {
        set({
          nodes: data.nodes,
          edges: data.edges,
          circuitName: data.name || 'Imported Circuit',
          code: data.code || '',
          selectedNodeId: null,
          validationMessages: [],
        });
      }
    } catch {
      // Invalid JSON - ignore
    }
  },
}));
