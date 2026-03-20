import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import { io } from 'socket.io-client';
import { useConnection } from './ConnectionContext';

const CameraContext = createContext();

export const useCamera = () => {
  const context = useContext(CameraContext);
  if (!context) {
    throw new Error('useCamera must be used within CameraProvider');
  }
  return context;
};

export const CameraProvider = ({ children }) => {
  const { serverUrl, isConnected } = useConnection();
  const [cameraState, setCameraState] = useState(null);
  const [socket, setSocket] = useState(null);

  useEffect(() => {
    if (isConnected && serverUrl) {
      const wsUrl = serverUrl.replace('http', 'ws');
      const newSocket = io(wsUrl, {
        path: '/socket.io',
        transports: ['websocket']
      });

      newSocket.on('connect', () => {
        console.log('WebSocket connected');
      });

      newSocket.on('camera_state', (data) => {
        setCameraState(data);
      });

      newSocket.on('disconnect', () => {
        console.log('WebSocket disconnected');
      });

      setSocket(newSocket);

      return () => {
        newSocket.close();
      };
    }
  }, [isConnected, serverUrl]);

  const refreshState = useCallback(async () => {
    if (!isConnected) return;

    try {
      const response = await fetch(`${serverUrl}/api/camera/state`);
      const data = await response.json();
      setCameraState(data);
    } catch (error) {
      console.error('Failed to refresh state:', error);
    }
  }, [isConnected, serverUrl]);

  const value = {
    cameraState,
    socket,
    refreshState
  };

  return (
    <CameraContext.Provider value={value}>
      {children}
    </CameraContext.Provider>
  );
};
