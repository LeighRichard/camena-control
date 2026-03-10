import React, { useState, useEffect } from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import PathEditor from './PathEditor';
import './AdvancedConfig.css';

function AdvancedConfig() {
  const { getApiClient, isConnected } = useConnection();
  const [activeTab, setActiveTab] = useState('camera');
  const [config, setConfig] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isConnected) {
      loadConfig();
    }
  }, [isConnected]);

  const loadConfig = async () => {
    try {
      const api = getApiClient();
      const response = await api.get('/api/system/config');
      setConfig(response.data);
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  const saveConfig = async () => {
    setIsSaving(true);
    try {
      const api = getApiClient();
      await api.put('/api/system/config', config);
      alert('Configuration saved successfully');
    } catch (error) {
      console.error('Failed to save config:', error);
      alert('Failed to save configuration');
    } finally {
      setIsSaving(false);
    }
  };

  const updateConfig = (section, key, value) => {
    setConfig(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }));
  };

  if (!config) {
    return <div className="advanced-config">Loading configuration...</div>;
  }

  return (
    <div className="advanced-config">
      <div className="config-tabs">
        <button 
          className={activeTab === 'camera' ? 'active' : ''}
          onClick={() => setActiveTab('camera')}
        >
          Camera
        </button>
        <button 
          className={activeTab === 'motion' ? 'active' : ''}
          onClick={() => setActiveTab('motion')}
        >
          Motion
        </button>
        <button 
          className={activeTab === 'detection' ? 'active' : ''}
          onClick={() => setActiveTab('detection')}
        >
          Detection
        </button>
        <button 
          className={activeTab === 'path' ? 'active' : ''}
          onClick={() => setActiveTab('path')}
        >
          Path Editor
        </button>
      </div>

      <div className="config-content">
        {activeTab === 'camera' && (
          <div className="config-section">
            <h3>Camera Settings</h3>
            <div className="form-group">
              <label>Resolution Width</label>
              <input
                type="number"
                value={config.camera?.width || 1280}
                onChange={(e) => updateConfig('camera', 'width', parseInt(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Resolution Height</label>
              <input
                type="number"
                value={config.camera?.height || 720}
                onChange={(e) => updateConfig('camera', 'height', parseInt(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Frame Rate</label>
              <input
                type="number"
                value={config.camera?.fps || 30}
                onChange={(e) => updateConfig('camera', 'fps', parseInt(e.target.value))}
              />
            </div>
          </div>
        )}

        {activeTab === 'motion' && (
          <div className="config-section">
            <h3>Motion Control Settings</h3>
            <div className="form-group">
              <label>Max Velocity (°/s or mm/s)</label>
              <input
                type="number"
                step="0.1"
                value={config.motion?.maxVelocity || 30}
                onChange={(e) => updateConfig('motion', 'maxVelocity', parseFloat(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Max Acceleration</label>
              <input
                type="number"
                step="0.1"
                value={config.motion?.maxAcceleration || 50}
                onChange={(e) => updateConfig('motion', 'maxAcceleration', parseFloat(e.target.value))}
              />
            </div>
            <h4>PID Parameters (Pan)</h4>
            <div className="pid-group">
              <div className="form-group">
                <label>Kp</label>
                <input
                  type="number"
                  step="0.01"
                  value={config.motion?.pidPan?.[0] || 1.0}
                  onChange={(e) => {
                    const newPid = [...(config.motion?.pidPan || [1, 0.1, 0.05])];
                    newPid[0] = parseFloat(e.target.value);
                    updateConfig('motion', 'pidPan', newPid);
                  }}
                />
              </div>
              <div className="form-group">
                <label>Ki</label>
                <input
                  type="number"
                  step="0.01"
                  value={config.motion?.pidPan?.[1] || 0.1}
                  onChange={(e) => {
                    const newPid = [...(config.motion?.pidPan || [1, 0.1, 0.05])];
                    newPid[1] = parseFloat(e.target.value);
                    updateConfig('motion', 'pidPan', newPid);
                  }}
                />
              </div>
              <div className="form-group">
                <label>Kd</label>
                <input
                  type="number"
                  step="0.01"
                  value={config.motion?.pidPan?.[2] || 0.05}
                  onChange={(e) => {
                    const newPid = [...(config.motion?.pidPan || [1, 0.1, 0.05])];
                    newPid[2] = parseFloat(e.target.value);
                    updateConfig('motion', 'pidPan', newPid);
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'detection' && (
          <div className="config-section">
            <h3>Detection Settings</h3>
            <div className="form-group">
              <label>Detection Threshold</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={config.detection?.threshold || 0.5}
                onChange={(e) => updateConfig('detection', 'threshold', parseFloat(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>Target Type</label>
              <select
                value={config.detection?.targetType || 'object'}
                onChange={(e) => updateConfig('detection', 'targetType', e.target.value)}
              >
                <option value="object">Object</option>
                <option value="aruco">ArUco Marker</option>
                <option value="face">Face</option>
              </select>
            </div>
          </div>
        )}

        {activeTab === 'path' && (
          <PathEditor />
        )}
      </div>

      <div className="config-actions">
        <button onClick={loadConfig}>Reset</button>
        <button onClick={saveConfig} disabled={isSaving} className="primary">
          {isSaving ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>
    </div>
  );
}

export default AdvancedConfig;
