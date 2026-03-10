import React, { createContext, useState, useContext, useCallback } from 'react';
import axios from 'axios';

const ConnectionContext = createContext();

export const useConnection = () => {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnection must be used within ConnectionProvider');
  }
  return context;
};

export const ConnectionProvider = ({ children }) => {
  const [serverUrl, setServerUrl] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [authToken, setAuthToken] = useState('');

  const connect = useCallback(async (url, token = '') => {
    try {
      const response = await axios.get(`${url}/api/camera/status`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });

      if (response.status === 200) {
        setServerUrl(url);
        setAuthToken(token);
        setIsConnected(true);

        // Save to electron store
        if (window.electron) {
          await window.electron.store.set('serverUrl', url);
          if (token) {
            await window.electron.store.set('authToken', token);
          }
        }

        return true;
      }
      return false;
    } catch (error) {
      console.error('Connection failed:', error);
      return false;
    }
  }, []);

  const disconnect = useCallback(async () => {
    setIsConnected(false);
    setServerUrl('');
    setAuthToken('');

    if (window.electron) {
      await window.electron.store.delete('serverUrl');
      await window.electron.store.delete('authToken');
    }
  }, []);

  const getApiClient = useCallback(() => {
    return axios.create({
      baseURL: serverUrl,
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : {}
    });
  }, [serverUrl, authToken]);

  const value = {
    serverUrl,
    isConnected,
    authToken,
    connect,
    disconnect,
    getApiClient
  };

  return (
    <ConnectionContext.Provider value={value}>
      {children}
    </ConnectionContext.Provider>
  );
};
