import React, { useState, useRef, useEffect } from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import { useCamera } from '../contexts/CameraContext';
import './HighResPreview.css';

function HighResPreview() {
  const { serverUrl } = useConnection();
  const { cameraState } = useCamera();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const containerRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  };

  const handleWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(prev => Math.max(0.5, Math.min(5, prev * delta)));
  };

  const handleMouseDown = (e) => {
    const startX = e.clientX - pan.x;
    const startY = e.clientY - pan.y;

    const handleMouseMove = (e) => {
      setPan({
        x: e.clientX - startX,
        y: e.clientY - startY
      });
    };

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div 
      ref={containerRef}
      className={`high-res-preview ${isFullscreen ? 'fullscreen' : ''}`}
      onWheel={handleWheel}
    >
      <div className="preview-controls">
        <button onClick={toggleFullscreen} title="Toggle Fullscreen (F11)">
          {isFullscreen ? '⛶' : '⛶'}
        </button>
        <button onClick={resetView} title="Reset View">
          ↺
        </button>
        <span className="zoom-indicator">{(zoom * 100).toFixed(0)}%</span>
      </div>

      <div 
        className="video-container"
        style={{
          transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
          cursor: zoom > 1 ? 'move' : 'default'
        }}
        onMouseDown={zoom > 1 ? handleMouseDown : undefined}
      >
        {serverUrl ? (
          <>
            <img
              src={`${serverUrl}/video_feed`}
              alt="Camera Feed"
              className="video-stream"
            />
            {cameraState?.targets && cameraState.targets.length > 0 && (
              <svg className="target-overlay">
                {cameraState.targets.map(target => (
                  <g key={target.id}>
                    <rect
                      x={target.boundingBox.x}
                      y={target.boundingBox.y}
                      width={target.boundingBox.width}
                      height={target.boundingBox.height}
                      fill="none"
                      stroke={target.id === cameraState.selectedTargetId ? '#4a9eff' : '#4caf50'}
                      strokeWidth="2"
                    />
                    <text
                      x={target.boundingBox.x}
                      y={target.boundingBox.y - 5}
                      fill={target.id === cameraState.selectedTargetId ? '#4a9eff' : '#4caf50'}
                      fontSize="14"
                    >
                      Target {target.id} - {target.distance.toFixed(0)}mm
                    </text>
                  </g>
                ))}
              </svg>
            )}
          </>
        ) : (
          <div className="no-video">No video stream available</div>
        )}
      </div>
    </div>
  );
}

export default HighResPreview;
