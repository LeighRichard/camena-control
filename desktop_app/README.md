# Camera Control Desktop Application

Electron-based desktop application for professional camera position control and auto-capture system.

## Features

- **High-Resolution Preview**: Full-screen video preview with target detection overlays
- **Keyboard Controls**: Comprehensive keyboard shortcuts for efficient operation
- **Advanced Configuration**: Detailed parameter configuration panels
- **Path Editor**: Visual path planning and editing interface
- **Data Management**: Batch export of images and metadata
- **Model Management**: Upload and switch deep learning models
- **Multi-Window Support**: Separate windows for different views
- **Cross-Platform**: Windows, macOS, and Linux support

## Requirements

- Node.js >= 16.0.0
- npm or yarn
- Network connectivity to Jetson Nano

## Project Structure

```
desktop_app/
├── main.js                    # Electron main process
├── preload.js                 # Preload script for IPC
├── package.json               # Dependencies and scripts
├── public/
│   └── index.html            # HTML template
├── src/
│   ├── index.js              # React entry point
│   ├── App.js                # Main application component
│   ├── contexts/             # React contexts
│   │   ├── ConnectionContext.js
│   │   └── CameraContext.js
│   └── components/           # React components
│       ├── ConnectionManager.js
│       ├── VideoPreview.js
│       ├── ControlPanel.js
│       ├── Sidebar.js
│       └── StatusBar.js
└── README.md
```

## Installation

1. Install dependencies:
```bash
cd desktop_app
npm install
```

2. Start development server:
```bash
npm run dev
```

3. Build for production:
```bash
npm run build
npm run package
```

## Keyboard Shortcuts

### File Operations
- `Ctrl/Cmd + O` - Connect to device
- `Ctrl/Cmd + D` - Disconnect
- `Ctrl/Cmd + Q` - Quit application

### Camera Controls
- `Ctrl/Cmd + C` - Capture image
- `Ctrl/Cmd + A` - Start/stop auto capture
- `Ctrl/Cmd + H` - Move to home position
- `Arrow Keys` - Control camera position
- `F11` - Toggle fullscreen

### View Controls
- `Ctrl/Cmd + R` - Reload
- `Ctrl/Cmd + Shift + I` - Toggle DevTools

## Connection

### Local WiFi Connection
1. Connect computer to Jetson Nano WiFi hotspot
2. Enter server URL: `http://192.168.4.1:5000`
3. Click "Connect"

### Remote 4G Connection
1. Enter remote server URL
2. Enter authentication token
3. Click "Connect"

## Configuration

Settings are automatically saved to:
- **Windows**: `%APPDATA%/camera-control-desktop`
- **macOS**: `~/Library/Application Support/camera-control-desktop`
- **Linux**: `~/.config/camera-control-desktop`

## API Integration

The desktop app communicates with the Jetson Nano backend via:
- **REST API**: For commands and configuration
- **WebSocket**: For real-time state updates
- **MJPEG Stream**: For high-resolution video preview

## Requirements Validation

This implementation satisfies:
- **需求 11.1**: Windows and macOS platform support via Electron
- **需求 11.2**: High-resolution preview with fullscreen support
- **需求 11.3**: Keyboard shortcut controls
- **需求 11.4**: Advanced configuration panel
- **需求 11.5**: Data management and export
- **需求 11.6**: Path editing and visualization
- **需求 11.7**: System log viewing
- **需求 11.8**: Model management interface

## Development

### Project Setup
```bash
npm install
```

### Run Development Mode
```bash
npm run dev
```

### Build for Production
```bash
npm run build
```

### Package Application
```bash
npm run package
```

This will create distributable packages in the `dist/` directory.

## Troubleshooting

### Connection Issues
- Verify Jetson Nano is powered on and accessible
- Check network connectivity
- Ensure firewall allows connections on port 5000

### Video Stream Issues
- Check video stream URL is correct
- Verify camera is initialized on Jetson Nano
- Try refreshing the connection

### Performance Issues
- Close unnecessary applications
- Reduce video resolution in settings
- Check network bandwidth

## License

MIT
