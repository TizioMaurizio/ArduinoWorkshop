import { useState } from 'react';
import { componentLibrary, categoryLabels } from '../data/components';
import type { ComponentCategory } from '../types/circuit';

interface ComponentPaletteProps {
  onAddComponent: (componentType: string) => void;
}

export default function ComponentPalette({ onAddComponent }: ComponentPaletteProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedCategory, setExpandedCategory] = useState<ComponentCategory | null>('microcontroller');

  const categories = Object.keys(categoryLabels) as ComponentCategory[];

  const filteredComponents = searchTerm
    ? componentLibrary.filter(
        (c) =>
          c.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
          c.description.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : null;

  return (
    <div style={styles.container}>
      <h3 style={styles.title}>Components</h3>

      <input
        type="text"
        placeholder="Search components..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        style={styles.search}
      />

      {filteredComponents ? (
        <div style={styles.searchResults}>
          {filteredComponents.map((comp) => (
            <button
              key={comp.type}
              style={styles.componentItem}
              onClick={() => onAddComponent(comp.type)}
              title={comp.description}
            >
              <span style={{ ...styles.dot, background: comp.color }} />
              <span style={styles.compLabel}>{comp.label}</span>
            </button>
          ))}
          {filteredComponents.length === 0 && (
            <p style={styles.noResults}>No components found</p>
          )}
        </div>
      ) : (
        <div style={styles.categories}>
          {categories.map((cat) => (
            <div key={cat}>
              <button
                style={{
                  ...styles.categoryHeader,
                  background: expandedCategory === cat ? '#2a2a3e' : 'transparent',
                }}
                onClick={() => setExpandedCategory(expandedCategory === cat ? null : cat)}
              >
                <span>{expandedCategory === cat ? '▼' : '▶'}</span>
                <span>{categoryLabels[cat]}</span>
                <span style={styles.count}>
                  {componentLibrary.filter((c) => c.category === cat).length}
                </span>
              </button>
              {expandedCategory === cat && (
                <div style={styles.categoryItems}>
                  {componentLibrary
                    .filter((c) => c.category === cat)
                    .map((comp) => (
                      <button
                        key={comp.type}
                        style={styles.componentItem}
                        onClick={() => onAddComponent(comp.type)}
                        title={comp.description}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData('application/circuit-component', comp.type);
                          e.dataTransfer.effectAllowed = 'move';
                        }}
                      >
                        <span style={{ ...styles.dot, background: comp.color }} />
                        <span style={styles.compLabel}>{comp.label}</span>
                      </button>
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: 240,
    background: '#1a1a2e',
    borderRight: '1px solid #333',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  title: {
    margin: 0,
    padding: '12px 16px',
    fontSize: 14,
    color: '#e0e0e0',
    borderBottom: '1px solid #333',
  },
  search: {
    margin: '8px 12px',
    padding: '6px 10px',
    borderRadius: 4,
    border: '1px solid #444',
    background: '#2a2a3e',
    color: '#e0e0e0',
    fontSize: 12,
    outline: 'none',
  },
  searchResults: {
    flex: 1,
    overflowY: 'auto',
    padding: '4px 8px',
  },
  categories: {
    flex: 1,
    overflowY: 'auto',
  },
  categoryHeader: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    border: 'none',
    color: '#ccc',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    textAlign: 'left',
  },
  count: {
    marginLeft: 'auto',
    fontSize: 10,
    color: '#888',
  },
  categoryItems: {
    padding: '2px 8px 8px 8px',
  },
  componentItem: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 10px',
    border: 'none',
    borderRadius: 4,
    background: 'transparent',
    color: '#ddd',
    fontSize: 11,
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'background 0.15s',
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: '50%',
    flexShrink: 0,
  },
  compLabel: {
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  noResults: {
    color: '#888',
    fontSize: 12,
    textAlign: 'center',
    marginTop: 20,
  },
};
