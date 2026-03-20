import React, { useState, useEffect } from 'react';
import './App.css';
import ConnectionManager from './components/ConnectionManager';
import VideoPreview from './components/VideoPreview';
import ControlPanel from './components/ControlPanel';
import StatusBar from './components/StatusBar';
import Sidebar from './components/Sidebar';
import { ConnectionProvider } from './contexts/ConnectionContext';
import { CameraProvider } from './contexts/CameraContext';

function App() {
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Setup menu event listeners
    if (window.electron) {
      window.electron.onMenuConnect(() => {
        // Handle connect menu action
      });

      window.electron.onMenuDisconnect(() => {
        setIsConnected(false);
      });

      window.electron.onMenuCapture(() => {
        // Handle capture menu action
      });

      window.electron.onMenuAutoCapture(() => {
        // Handle auto capture menu action
      });

      window.electron.onMenuHome(() => {
        // Handle home position menu action
      });
    }
  }, []);

  return (
    <ConnectionProvider>
      <CameraProvider>
        <div className="app">
          {!isConnected ? (
            <ConnectionManager onConnect={() => setIsConnected(true)} />
          ) : (
            <>
              <div className="main-content">
                <Sidebar />
                <div className="content-area">
                  <VideoPreview />
                  <ControlPanel />
                </div>
              </div>
              <StatusBar />
            </>
          )}
        </div>
      </CameraProvider>
    </ConnectionProvider>
  );
}

export default App;
