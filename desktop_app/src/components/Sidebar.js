import React from 'react';
import { useCamera } from '../contexts/CameraContext';
import './Sidebar.css';

function Sidebar() {
  const { cameraState } = useCamera();

  return (
    <div className="sidebar">
      <div className="sidebar-section">
        <h3>Camera Position</h3>
        {cameraState?.position ? (
          <div className="position-info">
            <div className="position-item">
              <span className="label">Pan:</span>
              <span className="value">{cameraState.position.pan.toFixed(1)}°</span>
            </div>
            <div className="position-item">
              <span className="label">Tilt:</span>
              <span className="value">{cameraState.position.tilt.toFixed(1)}°</span>
            </div>
            <div className="position-item">
              <span className="label">Rail:</span>
              <span className="value">{cameraState.position.rail.toFixed(1)}mm</span>
            </div>
          </div>
        ) : (
          <p className="no-data">No position data</p>
        )}
      </div>

      <div className="sidebar-section">
        <h3>Detected Targets</h3>
        {cameraState?.targets && cameraState.targets.length > 0 ? (
          <div className="targets-list">
            {cameraState.targets.map(target => (
              <div key={target.id} className="target-item">
                <span>Target {target.id}</span>
                <span>{target.distance.toFixed(0)}mm</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="no-data">No targets detected</p>
        )}
      </div>

      <div className="sidebar-section">
        <h3>System Status</h3>
        <div className="status-item">
          <span className="label">Status:</span>
          <span className={`status-badge ${cameraState?.status || 'unknown'}`}>
            {cameraState?.status || 'Unknown'}
          </span>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
