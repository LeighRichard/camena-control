import React from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import './StatusBar.css';

function StatusBar() {
  const { serverUrl, isConnected } = useConnection();

  return (
    <div className="status-bar">
      <div className="status-item">
        <span className={`connection-indicator ${isConnected ? 'connected' : 'disconnected'}`}></span>
        <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
      </div>
      {serverUrl && (
        <div className="status-item">
          <span>Server: {serverUrl}</span>
        </div>
      )}
      <div className="status-item">
        <span>Camera Control Desktop v1.0.0</span>
      </div>
    </div>
  );
}

export default StatusBar;
