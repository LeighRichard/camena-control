import React, { useState, useEffect } from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import './PathEditor.css';

function PathEditor() {
  const { getApiClient, isConnected } = useConnection();
  const [pathPoints, setPathPoints] = useState([]);
  const [pathName, setPathName] = useState('');
  const [selectedPoint, setSelectedPoint] = useState(null);

  const addPoint = () => {
    const newPoint = {
      id: Date.now(),
      pan: 0,
      tilt: 0,
      rail: 0,
      settleTime: 0.5,
      captureFrames: 5
    };
    setPathPoints([...pathPoints, newPoint]);
  };

  const updatePoint = (id, field, value) => {
    setPathPoints(pathPoints.map(point =>
      point.id === id ? { ...point, [field]: parseFloat(value) } : point
    ));
  };

  const deletePoint = (id) => {
    setPathPoints(pathPoints.filter(point => point.id !== id));
    if (selectedPoint === id) setSelectedPoint(null);
  };

  const savePath = async () => {
    if (!pathName) {
      alert('Please enter a path name');
      return;
    }

    try {
      const api = getApiClient();
      await api.post('/api/path/save', {
        name: pathName,
        points: pathPoints
      });
      alert('Path saved successfully');
    } catch (error) {
      console.error('Failed to save path:', error);
      alert('Failed to save path');
    }
  };

  const loadPath = async () => {
    try {
      const api = getApiClient();
      const response = await api.get('/api/path/list');
      // Handle path loading
    } catch (error) {
      console.error('Failed to load paths:', error);
    }
  };

  return (
    <div className="path-editor">
      <div className="path-header">
        <input
          type="text"
          placeholder="Path Name"
          value={pathName}
          onChange={(e) => setPathName(e.target.value)}
          className="path-name-input"
        />
        <button onClick={addPoint}>Add Point</button>
        <button onClick={savePath} className="primary">Save Path</button>
      </div>

      <div className="path-content">
        <div className="path-list">
          <h4>Path Points ({pathPoints.length})</h4>
          {pathPoints.length === 0 ? (
            <p className="empty-message">No points added yet</p>
          ) : (
            <div className="points-list">
              {pathPoints.map((point, index) => (
                <div
                  key={point.id}
                  className={`point-item ${selectedPoint === point.id ? 'selected' : ''}`}
                  onClick={() => setSelectedPoint(point.id)}
                >
                  <div className="point-number">{index + 1}</div>
                  <div className="point-info">
                    <div>Pan: {point.pan}°</div>
                    <div>Tilt: {point.tilt}°</div>
                    <div>Rail: {point.rail}mm</div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deletePoint(point.id);
                    }}
                    className="delete-button"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="point-editor">
          {selectedPoint ? (
            <>
              <h4>Edit Point</h4>
              {pathPoints.find(p => p.id === selectedPoint) && (
                <div className="editor-form">
                  <div className="form-group">
                    <label>Pan (degrees)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={pathPoints.find(p => p.id === selectedPoint).pan}
                      onChange={(e) => updatePoint(selectedPoint, 'pan', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Tilt (degrees)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={pathPoints.find(p => p.id === selectedPoint).tilt}
                      onChange={(e) => updatePoint(selectedPoint, 'tilt', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Rail (mm)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={pathPoints.find(p => p.id === selectedPoint).rail}
                      onChange={(e) => updatePoint(selectedPoint, 'rail', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Settle Time (seconds)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={pathPoints.find(p => p.id === selectedPoint).settleTime}
                      onChange={(e) => updatePoint(selectedPoint, 'settleTime', e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Capture Frames</label>
                    <input
                      type="number"
                      value={pathPoints.find(p => p.id === selectedPoint).captureFrames}
                      onChange={(e) => updatePoint(selectedPoint, 'captureFrames', e.target.value)}
                    />
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="empty-editor">
              <p>Select a point to edit</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default PathEditor;
