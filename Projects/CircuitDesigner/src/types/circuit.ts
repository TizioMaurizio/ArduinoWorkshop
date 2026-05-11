export type PinType = 'digital' | 'analog' | 'power' | 'ground' | 'pwm' | 'i2c' | 'spi' | 'uart';

export interface PinDefinition {
  id: string;
  label: string;
  type: PinType;
  direction: 'input' | 'output' | 'bidirectional';
  voltage?: number;
  position: 'left' | 'right' | 'top' | 'bottom';
  index: number; // position order on that side
}

export interface ComponentDefinition {
  type: string;
  label: string;
  category: ComponentCategory;
  description: string;
  pins: PinDefinition[];
  color: string;
  width: number;
  height: number;
  icon?: string;
}

export type ComponentCategory =
  | 'microcontroller'
  | 'sensor'
  | 'actuator'
  | 'passive'
  | 'power'
  | 'display'
  | 'communication'
  | 'input';

export interface CircuitComponent {
  id: string;
  definitionType: string;
  position: { x: number; y: number };
  rotation: number;
  properties: Record<string, string | number>;
}

export interface Wire {
  id: string;
  sourceComponentId: string;
  sourcePinId: string;
  targetComponentId: string;
  targetPinId: string;
}

export interface Circuit {
  id: string;
  name: string;
  components: CircuitComponent[];
  wires: Wire[];
  createdAt: string;
  updatedAt: string;
}

export interface ValidationMessage {
  severity: 'error' | 'warning' | 'info';
  message: string;
  componentIds?: string[];
  wireIds?: string[];
}
