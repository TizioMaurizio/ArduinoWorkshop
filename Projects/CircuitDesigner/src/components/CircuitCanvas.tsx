import { useCallback, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  ConnectionMode,
  type ReactFlowInstance,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useCircuitStore, type CircuitNode } from '../store/circuitStore';
import CircuitComponentNode from './CircuitComponentNode';

const nodeTypes = {
  circuitComponent: CircuitComponentNode,
};

export default function CircuitCanvas() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect, addComponent, setSelectedNode, setSelectedEdge } =
    useCircuitStore();
  const reactFlowInstance = useRef<ReactFlowInstance<CircuitNode, Edge> | null>(null);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const componentType = event.dataTransfer.getData('application/circuit-component');
      if (!componentType || !reactFlowInstance.current) return;

      const position = reactFlowInstance.current.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      addComponent(componentType, position);
    },
    [addComponent]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  return (
    <div style={{ flex: 1, height: '100%' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        onInit={(instance: ReactFlowInstance<CircuitNode, Edge>) => { reactFlowInstance.current = instance; }}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onNodeClick={(_, node) => setSelectedNode(node.id)}
        onEdgeClick={(_, edge) => setSelectedEdge(edge.id)}
        onPaneClick={() => { setSelectedNode(null); setSelectedEdge(null); }}
        connectionMode={ConnectionMode.Loose}
        fitView
        snapToGrid
        snapGrid={[16, 16]}
        defaultEdgeOptions={{
          type: 'smoothstep',
          animated: true,
          style: { stroke: '#b0b0b0', strokeWidth: 2 },
        }}
        style={{ background: '#0d0d1a' }}
      >
        <Background color="#333" gap={16} size={1} />
        <Controls
          style={{ background: '#2a2a3e', borderRadius: 6, border: '1px solid #444' }}
        />
        <MiniMap
          nodeColor={(n) => {
            const data = n.data as { componentType?: string };
            if (data.componentType?.includes('arduino')) return '#00979D';
            if (data.componentType?.includes('esp')) return '#E7352C';
            return '#666';
          }}
          style={{ background: '#1a1a2e', border: '1px solid #333' }}
        />
      </ReactFlow>
    </div>
  );
}
