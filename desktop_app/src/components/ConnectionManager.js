import React, { useState, useEffect } from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import './ConnectionManager.css';

function ConnectionManager({ onConnect }) {
  const { connect } = useConnection();
  const [url, setUrl] = useState('http://192.168.4.1:5000');
  const [token, setToken] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // Load saved connection settings
    if (window.electron) {
      window.electron.store.get('serverUrl').then(savedUrl => {
        if (savedUrl) setUrl(savedUrl);
      });
      window.electron.store.get('authToken').then(savedToken => {
        if (savedToken) setToken(savedToken);
      });
    }
  }, []);

  const handleConnect = async () => {
    setIsConnecting(true);
    setError('');

    try {
      const success = await connect(url, token);
      if (success) {
        onConnect();
      } else {
        setError('Failed to connect to server');
      }
    } catch (err) {
      setError(err.message || 'Connection error');
    } finally {
      setIsConnecting(false);
    }
  };

  return (
    <div className="connection-manager">
      <div className="connection-card">
        <h1>Camera Control Desktop</h1>
        <p className="subtitle">Connect to your camera system</p>

        <div className="form-group">
          <label>Server URL</label>
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://192.168.4.1:5000"
            disabled={isConnecting}
          />
        </div>

        <div className="form-group">
          <label>Authentication Token (Optional)</label>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Enter token for remote access"
            disabled={isConnecting}
          />
        </div>

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        <button
          className="connect-button"
          onClick={handleConnect}
          disabled={isConnecting || !url}
        >
          {isConnecting ? 'Connecting...' : 'Connect'}
        </button>

        <div className="connection-info">
          <h3>Connection Modes:</h3>
          <ul>
            <li><strong>Local WiFi:</strong> http://192.168.4.1:5000</li>
            <li><strong>Remote 4G:</strong> Use your remote server URL with token</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default ConnectionManager;
