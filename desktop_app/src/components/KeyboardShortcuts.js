import React, { useState } from 'react';
import './KeyboardShortcuts.css';

function KeyboardShortcuts() {
  const [isOpen, setIsOpen] = useState(false);

  const shortcuts = [
    { category: 'Camera Control', items: [
      { keys: ['↑', '↓', '←', '→'], description: 'Control Pan/Tilt' },
      { keys: ['W', 'S'], description: 'Control Rail (Forward/Backward)' },
      { keys: ['Ctrl', '+', 'Arrows'], description: 'Fine control (0.1° steps)' },
      { keys: ['Space'], description: 'Capture image' },
      { keys: ['Ctrl', '+', 'H'], description: 'Move to home position' },
    ]},
    { category: 'Preset Positions', items: [
      { keys: ['1'], description: 'Position 1 (Left)' },
      { keys: ['2'], description: 'Position 2 (Center)' },
      { keys: ['3'], description: 'Position 3 (Right)' },
    ]},
    { category: 'View Controls', items: [
      { keys: ['F11'], description: 'Toggle fullscreen' },
      { keys: ['Ctrl', '+', 'R'], description: 'Reload' },
      { keys: ['Ctrl', '+', 'Shift', '+', 'I'], description: 'Toggle DevTools' },
    ]},
    { category: 'Application', items: [
      { keys: ['Ctrl', '+', 'O'], description: 'Connect' },
      { keys: ['Ctrl', '+', 'D'], description: 'Disconnect' },
      { keys: ['Ctrl', '+', 'Q'], description: 'Quit' },
    ]},
  ];

  return (
    <>
      <button 
        className="shortcuts-button"
        onClick={() => setIsOpen(true)}
        title="Keyboard Shortcuts"
      >
        ⌨️
      </button>

      {isOpen && (
        <div className="shortcuts-modal" onClick={() => setIsOpen(false)}>
          <div className="shortcuts-content" onClick={(e) => e.stopPropagation()}>
            <div className="shortcuts-header">
              <h2>Keyboard Shortcuts</h2>
              <button onClick={() => setIsOpen(false)}>✕</button>
            </div>

            <div className="shortcuts-body">
              {shortcuts.map((category, idx) => (
                <div key={idx} className="shortcut-category">
                  <h3>{category.category}</h3>
                  <div className="shortcut-list">
                    {category.items.map((item, itemIdx) => (
                      <div key={itemIdx} className="shortcut-item">
                        <div className="shortcut-keys">
                          {item.keys.map((key, keyIdx) => (
                            <React.Fragment key={keyIdx}>
                              <kbd>{key}</kbd>
                              {keyIdx < item.keys.length - 1 && <span className="plus">+</span>}
                            </React.Fragment>
                          ))}
                        </div>
                        <div className="shortcut-description">{item.description}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default KeyboardShortcuts;
