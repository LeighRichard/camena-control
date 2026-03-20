import { useEffect, useCallback } from 'react';
import { useConnection } from '../contexts/ConnectionContext';

const useKeyboardControls = (enabled = true) => {
  const { getApiClient, isConnected } = useConnection();

  const adjustPosition = useCallback(async (delta) => {
    if (!isConnected) return;

    try {
      const api = getApiClient();
      await api.post('/api/camera/position/adjust', delta);
    } catch (error) {
      console.error('Failed to adjust position:', error);
    }
  }, [isConnected, getApiClient]);

  const capture = useCallback(async () => {
    if (!isConnected) return;

    try {
      const api = getApiClient();
      await api.post('/api/camera/capture');
    } catch (error) {
      console.error('Failed to capture:', error);
    }
  }, [isConnected, getApiClient]);

  const homePosition = useCallback(async () => {
    if (!isConnected) return;

    try {
      const api = getApiClient();
      await api.post('/api/camera/position', {
        pan: 0,
        tilt: 0,
        rail: 0
      });
    } catch (error) {
      console.error('Failed to move to home:', error);
    }
  }, [isConnected, getApiClient]);

  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e) => {
      // Prevent default for arrow keys
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault();
      }

      const step = e.ctrlKey || e.metaKey ? 0.1 : 1; // Fine control with Ctrl/Cmd

      switch (e.key) {
        // Arrow keys for Pan/Tilt
        case 'ArrowUp':
          adjustPosition({ tiltDelta: step });
          break;
        case 'ArrowDown':
          adjustPosition({ tiltDelta: -step });
          break;
        case 'ArrowLeft':
          adjustPosition({ panDelta: -step });
          break;
        case 'ArrowRight':
          adjustPosition({ panDelta: step });
          break;

        // W/S for Rail
        case 'w':
        case 'W':
          adjustPosition({ railDelta: step * 10 });
          break;
        case 's':
        case 'S':
          adjustPosition({ railDelta: -step * 10 });
          break;

        // Space for capture
        case ' ':
          e.preventDefault();
          capture();
          break;

        // H for home
        case 'h':
        case 'H':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            homePosition();
          }
          break;

        // Number keys for preset positions
        case '1':
          adjustPosition({ pan: -45, tilt: 0, rail: 0 });
          break;
        case '2':
          adjustPosition({ pan: 0, tilt: 0, rail: 0 });
          break;
        case '3':
          adjustPosition({ pan: 45, tilt: 0, rail: 0 });
          break;

        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [enabled, adjustPosition, capture, homePosition]);

  return {
    adjustPosition,
    capture,
    homePosition
  };
};

export default useKeyboardControls;
