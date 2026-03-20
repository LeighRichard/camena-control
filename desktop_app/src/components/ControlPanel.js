import React from 'react';
import './ControlPanel.css';

function ControlPanel() {
  return (
    <div className="control-panel">
      <div className="control-section">
        <h3>Quick Controls</h3>
        <div className="button-group">
          <button className="control-button">Capture</button>
          <button className="control-button">Auto Capture</button>
          <button className="control-button">Home</button>
        </div>
      </div>
    </div>
  );
}

export default ControlPanel;
