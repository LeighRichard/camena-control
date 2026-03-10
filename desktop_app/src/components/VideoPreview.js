import React from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import './VideoPreview.css';

function VideoPreview() {
  const { serverUrl } = useConnection();

  return (
    <div className="video-preview">
      <div className="video-container">
        {serverUrl ? (
          <img
            src={`${serverUrl}/video_feed`}
            alt="Camera Feed"
            className="video-stream"
          />
        ) : (
          <div className="no-video">No video stream available</div>
        )}
      </div>
    </div>
  );
}

export default VideoPreview;
