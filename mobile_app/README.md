# Camera Control Mobile App

Flutter mobile application for controlling the camera position control and auto-capture system.

## Features

- **Device Connection**: Connect via WiFi hotspot or 4G remote access
- **Real-time Preview**: View live camera feed with target detection overlays
- **Position Control**: Control camera position using joystick/sliders
- **Target Selection**: Manual target selection from detected objects
- **Auto Capture**: Start/stop automatic capture sequences
- **Capture History**: View and download captured images
- **System Configuration**: Configure system parameters

## Requirements

- Flutter SDK >= 3.0.0
- iOS 12.0+ / Android 5.0+
- Network connectivity (WiFi or 4G)

## Project Structure

```
mobile_app/
├── lib/
│   ├── main.dart                 # App entry point
│   ├── models/                   # Data models
│   │   ├── camera_state.dart
│   │   └── capture_history.dart
│   ├── providers/                # State management
│   │   ├── connection_provider.dart
│   │   ├── camera_provider.dart
│   │   └── control_provider.dart
│   ├── services/                 # API services
│   │   └── api_service.dart
│   ├── screens/                  # UI screens
│   │   ├── home_screen.dart
│   │   ├── connection_screen.dart
│   │   ├── preview_screen.dart
│   │   ├── history_screen.dart
│   │   └── settings_screen.dart
│   └── widgets/                  # Reusable widgets
│       ├── joystick_control.dart
│       ├── target_overlay.dart
│       └── video_player_widget.dart
└── pubspec.yaml
```

## Setup

1. Install Flutter dependencies:
```bash
cd mobile_app
flutter pub get
```

2. Run on device/emulator:
```bash
flutter run
```

## Connection Modes

### WiFi Hotspot Mode
1. Connect phone to Jetson Nano WiFi hotspot
2. Enter IP address (default: 192.168.4.1)
3. Tap "Connect"

### 4G Remote Mode
1. Enter remote server URL
2. Enter authentication token
3. Tap "Connect"

## API Integration

The app communicates with the Jetson Nano backend via:
- REST API for commands and configuration
- WebSocket for real-time state updates
- MJPEG stream for video preview

## Requirements Validation

This implementation satisfies:
- **需求 10.1**: iOS and Android platform support via Flutter
- **需求 10.7**: WiFi hotspot and 4G remote connection modes
- **需求 10.2**: Real-time preview display
- **需求 10.4**: Target detection result display and manual selection
- **需求 10.3**: Position control via sliders/joystick
- **需求 10.5**: One-tap capture and auto-capture control
- **需求 10.6**: Capture history viewing and download
- **需求 10.8**: System parameter configuration interface
