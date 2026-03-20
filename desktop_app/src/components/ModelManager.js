import React, { useState, useEffect } from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import './ModelManager.css';

function ModelManager() {
  const { getApiClient, isConnected } = useConnection();
  const [models, setModels] = useState([]);
  const [activeModel, setActiveModel] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    if (isConnected) {
      loadModels();
    }
  }, [isConnected]);

  const loadModels = async () => {
    try {
      const api = getApiClient();
      const response = await api.get('/api/model/list');
      setModels(response.data.models);
      setActiveModel(response.data.activeModel);
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  };

  const handleFileSelect = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('model', file);
      formData.append('name', file.name);

      const api = getApiClient();
      await api.post('/api/model/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
        }
      });

      alert('Model uploaded successfully');
      loadModels();
    } catch (error) {
      console.error('Failed to upload model:', error);
      alert('Failed to upload model');
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const switchModel = async (modelId) => {
    try {
      const api = getApiClient();
      await api.post('/api/model/switch', { modelId });
      setActiveModel(modelId);
      alert('Model switched successfully');
    } catch (error) {
      console.error('Failed to switch model:', error);
      alert('Failed to switch model');
    }
  };

  const deleteModel = async (modelId) => {
    if (!confirm('Are you sure you want to delete this model?')) {
      return;
    }

    try {
      const api = getApiClient();
      await api.delete(`/api/model/${modelId}`);
      alert('Model deleted successfully');
      loadModels();
    } catch (error) {
      console.error('Failed to delete model:', error);
      alert('Failed to delete model');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  return (
    <div className="model-manager">
      <div className="manager-header">
        <h2>Model Management</h2>
        <div className="upload-section">
          <input
            type="file"
            id="model-upload"
            accept=".onnx,.trt,.engine"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
            disabled={isUploading}
          />
          <label htmlFor="model-upload" className={`upload-button ${isUploading ? 'disabled' : ''}`}>
            {isUploading ? `Uploading... ${uploadProgress}%` : 'Upload Model'}
          </label>
        </div>
      </div>

      {isUploading && (
        <div className="upload-progress">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
          </div>
        </div>
      )}

      <div className="models-list">
        {models.length === 0 ? (
          <div className="empty-state">
            <p>No models available</p>
            <p className="hint">Upload a model to get started</p>
          </div>
        ) : (
          models.map(model => (
            <div key={model.id} className={`model-card ${model.id === activeModel ? 'active' : ''}`}>
              <div className="model-icon">
                {model.id === activeModel ? '✓' : '🤖'}
              </div>
              <div className="model-info">
                <h3>{model.name}</h3>
                <div className="model-details">
                  <span>Type: {model.type}</span>
                  <span>Size: {formatFileSize(model.size)}</span>
                  {model.accuracy && <span>Accuracy: {model.accuracy}%</span>}
                  {model.fps && <span>Speed: {model.fps} FPS</span>}
                </div>
                {model.id === activeModel && (
                  <div className="active-badge">Active</div>
                )}
              </div>
              <div className="model-actions">
                {model.id !== activeModel && (
                  <button onClick={() => switchModel(model.id)} className="switch-button">
                    Switch
                  </button>
                )}
                <button onClick={() => deleteModel(model.id)} className="delete-button">
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="model-info-section">
        <h3>Supported Model Formats</h3>
        <ul>
          <li><strong>ONNX (.onnx)</strong> - Open Neural Network Exchange format</li>
          <li><strong>TensorRT (.trt, .engine)</strong> - NVIDIA TensorRT optimized models</li>
        </ul>
        <p className="note">
          Models will be automatically optimized for Jetson Nano GPU after upload.
        </p>
      </div>
    </div>
  );
}

export default ModelManager;
