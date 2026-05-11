import { describe, it, expect } from 'vitest';
import { componentLibrary, getComponentByType, getComponentsByCategory } from '../data/components';
import type { ComponentCategory } from '../types/circuit';

describe('componentLibrary', () => {
  it('has components in all categories', () => {
    const categories: ComponentCategory[] = [
      'microcontroller', 'sensor', 'actuator', 'passive',
      'power', 'display', 'communication', 'input',
    ];
    for (const cat of categories) {
      const items = getComponentsByCategory(cat);
      expect(items.length).toBeGreaterThan(0);
    }
  });

  it('has unique component types', () => {
    const types = componentLibrary.map((c) => c.type);
    const uniqueTypes = new Set(types);
    expect(uniqueTypes.size).toBe(types.length);
  });

  it('all components have at least one pin', () => {
    for (const comp of componentLibrary) {
      expect(comp.pins.length).toBeGreaterThan(0);
    }
  });

  it('all pins have unique IDs within a component', () => {
    for (const comp of componentLibrary) {
      const pinIds = comp.pins.map((p) => p.id);
      const uniqueIds = new Set(pinIds);
      expect(uniqueIds.size).toBe(pinIds.length);
    }
  });

  it('getComponentByType returns correct component', () => {
    const uno = getComponentByType('arduino-uno');
    expect(uno).toBeDefined();
    expect(uno!.label).toBe('Arduino Uno');
    expect(uno!.category).toBe('microcontroller');
  });

  it('getComponentByType returns undefined for unknown type', () => {
    expect(getComponentByType('unknown-thing')).toBeUndefined();
  });

  it('microcontrollers have power and ground pins', () => {
    const mcus = getComponentsByCategory('microcontroller');
    for (const mcu of mcus) {
      const hasPower = mcu.pins.some((p) => p.type === 'power');
      const hasGround = mcu.pins.some((p) => p.type === 'ground');
      expect(hasPower).toBe(true);
      expect(hasGround).toBe(true);
    }
  });

  it('Arduino Uno has expected pin count', () => {
    const uno = getComponentByType('arduino-uno')!;
    expect(uno.pins.length).toBe(25); // 11 left + 14 right
  });

  it('ESP32 has I2C pins', () => {
    const esp = getComponentByType('esp32')!;
    const i2cPins = esp.pins.filter((p) => p.type === 'i2c');
    expect(i2cPins.length).toBeGreaterThanOrEqual(2);
  });

  it('all components have valid dimensions', () => {
    for (const comp of componentLibrary) {
      expect(comp.width).toBeGreaterThan(0);
      expect(comp.height).toBeGreaterThan(0);
    }
  });

  it('all pin positions are valid', () => {
    const validPositions = ['left', 'right', 'top', 'bottom'];
    for (const comp of componentLibrary) {
      for (const pin of comp.pins) {
        expect(validPositions).toContain(pin.position);
      }
    }
  });
});
