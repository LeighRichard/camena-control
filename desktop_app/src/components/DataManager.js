import React, { useState, useEffect } from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import './DataManager.css';

function DataManager() {
  const { getApiClient, isConnected } = useConnection();
  const [captures, setCaptures] = useState([]);
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [isExporting, setIsExporting] = useState(false);
  const [logs, setLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('images');

  useEffect(() => {
    if (isConnected) {
      loadCaptures();
      loadLogs();
    }
  }, [isConnected]);

  const loadCaptures = async () => {
    try {
      const api = getApiClient();
      const response = await api.get('/api/camera/history');
      setCaptures(response.data);
    } catch (error) {
      console.error('Failed to load captures:', error);
    }
  };

  const loadLogs = async () => {
    try {
      const api = getApiClient();
      const response = await api.get('/api/logs');
      setLogs(response.data);
    } catch (error) {
      console.error('Failed to load logs:', error);
    }
  };

  const toggleSelection = (id) => {
    const newSelection = new Set(selectedItems);
    if (newSelection.has(id)) {
      newSelection.delete(id);
    } else {
      newSelection.add(id);
    }
    setSelectedItems(newSelection);
  };

  const selectAll = () => {
    if (selectedItems.size === captures.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(captures.map(c => c.id)));
    }
  };

  const exportSelected = async () => {
    if (selectedItems.size === 0) {
      alert('Please select items to export');
      return;
    }

    setIsExporting(true);
    try {
      const api = getApiClient();
      const selectedCaptures = captures.filter(c => selectedItems.has(c.id));
      
      // Request export
      const response = await api.post('/api/export/images', {
        captures: selectedCaptures.map(c => c.id)
      });

      // Download the export file
      const downloadUrl = `${api.defaults.baseURL}/api/export/download/${response.data.exportId}`;
      window.open(downloadUrl, '_blank');

      alert('Export started. Download will begin shortly.');
    } catch (error) {
      console.error('Failed to export:', error);
      alert('Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const exportMetadata = async () => {
    try {
      const api = getApiClient();
      const selectedCaptures = captures.filter(c => selectedItems.has(c.id));
      
      const metadata = selectedCaptures.map(c => ({
        id: c.id,
        timestamp: c.timestamp,
        position: c.position,
        imagePath: c.imagePath
      }));

      const blob = new Blob([JSON.stringify(metadata, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `metadata_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export metadata:', error);
    }
  };

  return (
    <div className="data-manager">
      <div className="manager-tabs">
        <button
          className={activeTab === 'images' ? 'active' : ''}
          onClick={() => setActiveTab('images')}
        >
          Images ({captures.length})
        </button>
        <button
          className={activeTab === 'logs' ? 'active' : ''}
          onClick={() => setActiveTab('logs')}
        >
          System Logs
        </button>
      </div>

      {activeTab === 'images' && (
        <div className="images-tab">
          <div className="toolbar">
            <button onClick={selectAll}>
              {selectedItems.size === captures.length ? 'Deselect All' : 'Select All'}
            </button>
            <button onClick={exportSelected} disabled={selectedItems.size === 0 || isExporting}>
              {isExporting ? 'Exporting...' : `Export Selected (${selectedItems.size})`}
            </button>
            <button onClick={exportMetadata} disabled={selectedItems.size === 0}>
              Export Metadata
            </button>
            <button onClick={loadCaptures}>Refresh</button>
          </div>

          <div className="image-grid">
            {captures.map(capture => (
              <div
                key={capture.id}
                className={`image-card ${selectedItems.has(capture.id) ? 'selected' : ''}`}
                onClick={() => toggleSelection(capture.id)}
              >
                <div className="image-placeholder">
                  <span>📷</span>
                </div>
                <div className="image-info">
                  <div className="image-date">
                    {new Date(capture.timestamp).toLocaleString()}
                  </div>
                  <div className="image-position">
                    Pan: {capture.position.pan.toFixed(1)}° | 
                    Tilt: {capture.position.tilt.toFixed(1)}° | 
                    Rail: {capture.position.rail.toFixed(1)}mm
                  </div>
                </div>
                {selectedItems.has(capture.id) && (
                  <div className="selection-indicator">✓</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'logs' && (
        <div className="logs-tab">
          <div className="toolbar">
            <button onClick={loadLogs}>Refresh</button>
          </div>
          <div className="logs-container">
            {logs.map((log, index) => (
              <div key={index} className={`log-entry ${log.level}`}>
                <span className="log-time">{new Date(log.timestamp).toLocaleTimeString()}</span>
                <span className="log-level">{log.level}</span>
                <span className="log-message">{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default DataManager;
