# Remote Access Guide

This guide explains how to set up and use remote access features for the camera position control system.

## Features

1. **4G Connectivity** - Connect to the internet via 4G/LTE modem
2. **Network Tunnel** - Access the system from anywhere using FRP or ngrok
3. **Authentication** - Secure access with JWT-based authentication
4. **Adaptive Streaming** - Automatic video quality adjustment based on network conditions

## Requirements

### Hardware
- 4G USB modem (e.g., Huawei E3372, ZTE MF823, Quectel EC25)
- SIM card with data plan
- USB port on Jetson Nano

### Software Dependencies

```bash
# For 4G connectivity (QMI protocol)
sudo apt-get install libqmi-utils udhcpc

# For 4G connectivity (PPP protocol)
sudo apt-get install ppp

# For FRP tunnel
wget https://github.com/fatedier/frp/releases/download/v0.52.0/frp_0.52.0_linux_arm64.tar.gz
tar -xzf frp_0.52.0_linux_arm64.tar.gz
sudo cp frp_0.52.0_linux_arm64/frpc /usr/local/bin/

# For ngrok tunnel
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz
tar -xzf ngrok-v3-stable-linux-arm64.tgz
sudo mv ngrok /usr/local/bin/

# Python dependencies
pip install pyjwt pyyaml requests
```

## Configuration

### 1. Configure 4G Modem

Edit `config/remote_access.yaml`:

```yaml
modem:
  enabled: true
  protocol: qmi  # or ppp
  apn: internet  # Change to your carrier's APN
  device: /dev/cdc-wdm0
  interface: wwan0
```

**Common APNs:**
- China Mobile: cmnet
- China Unicom: 3gnet
- China Telecom: ctnet
- AT&T (US): broadband
- Verizon (US): vzwinternet
- T-Mobile (US): fast.t-mobile.com

### 2. Configure Network Tunnel

#### Option A: FRP (Recommended for self-hosted)

1. Set up FRP server on a public server:
```bash
# On your public server
wget https://github.com/fatedier/frp/releases/download/v0.52.0/frp_0.52.0_linux_amd64.tar.gz
tar -xzf frp_0.52.0_linux_amd64.tar.gz
cd frp_0.52.0_linux_amd64

# Edit frps.ini
cat > frps.ini << EOF
[common]
bind_port = 7000
token = your-secret-token
subdomain_host = yourdomain.com
EOF

# Start FRP server
./frps -c frps.ini
```

2. Configure client in `config/remote_access.yaml`:
```yaml
tunnel:
  enabled: true
  type: frp
  frp:
    server_addr: your-server-ip
    server_port: 7000
    token: your-secret-token
    local_port: 5000
    subdomain: camera-system
```

#### Option B: ngrok (Easier setup, paid service)

1. Sign up at https://ngrok.com and get authtoken

2. Configure in `config/remote_access.yaml`:
```yaml
tunnel:
  enabled: true
  type: ngrok
  ngrok:
    authtoken: your-ngrok-authtoken
    region: us
    local_port: 5000
```

### 3. Configure Authentication

Edit `config/remote_access.yaml`:

```yaml
auth:
  enabled: true
  secret_key: change-this-to-random-secret-key  # Generate with: openssl rand -hex 32
  token_expiry_hours: 24
  
  users:
    - username: admin
      password: admin123  # CHANGE THIS!
      role: admin
    - username: operator
      password: operator123
      role: operator
```

**User Roles:**
- **admin**: Full access (view, control, configure, manage users)
- **operator**: View, control, capture
- **viewer**: View only

### 4. Configure Adaptive Streaming

Edit `config/remote_access.yaml`:

```yaml
streaming:
  enabled: true
  initial_quality: medium
  adaptation_interval: 5
  bandwidth_safety_margin: 0.8
```

**Quality Levels:**
- **low**: 640x480 @ 10fps (500 kbps)
- **medium**: 1280x720 @ 15fps (1500 kbps)
- **high**: 1280x720 @ 25fps (3000 kbps)
- **ultra**: 1920x1080 @ 30fps (5000 kbps)

## Usage

### Starting the System

```bash
cd jetson
python examples/remote_access_example.py
```

### API Authentication

All API requests (except `/api/auth/login`) require authentication:

```bash
# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Response: {"token": "eyJ0eXAiOiJKV1QiLCJhbGc...", "username": "admin", "role": "admin"}

# Use token in subsequent requests
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  http://localhost:5000/api/status
```

### Web Interface

Access the web interface at:
- Local: http://localhost:5000
- Remote (FRP): http://camera-system.yourdomain.com
- Remote (ngrok): https://xxxxx.ngrok.io

Login with configured credentials.

## Monitoring

### Check 4G Connection

```bash
# Check modem status
qmicli -d /dev/cdc-wdm0 --nas-get-signal-strength
qmicli -d /dev/cdc-wdm0 --wds-get-packet-service-status

# Check network interface
ip addr show wwan0
ping -I wwan0 8.8.8.8
```

### Check Tunnel Status

```bash
# FRP
ps aux | grep frpc
curl http://localhost:7400/api/status  # FRP admin API

# ngrok
curl http://localhost:4040/api/tunnels  # ngrok API
```

### View Logs

```bash
# Application logs
tail -f /var/log/camera-system.log

# System logs
journalctl -u camera-system -f
```

## Troubleshooting

### 4G Modem Not Detected

```bash
# Check USB devices
lsusb

# Check if modem is recognized
ls /dev/cdc-wdm*
ls /dev/ttyUSB*

# Install modem drivers
sudo apt-get install modemmanager
sudo mmcli -L
```

### Cannot Connect to 4G

1. Check SIM card is inserted and activated
2. Verify APN settings for your carrier
3. Check signal strength: `qmicli -d /dev/cdc-wdm0 --nas-get-signal-strength`
4. Try manual connection: `sudo qmi-network /dev/cdc-wdm0 start`

### Tunnel Connection Failed

**FRP:**
1. Check server is running: `telnet your-server-ip 7000`
2. Verify token matches server configuration
3. Check firewall allows port 7000

**ngrok:**
1. Verify authtoken is correct
2. Check ngrok account limits
3. Try different region

### Authentication Issues

1. Verify secret_key is set in config
2. Check token hasn't expired (default 24 hours)
3. Clear browser cookies/cache
4. Generate new token by logging in again

### Poor Video Quality

1. Check network bandwidth: `speedtest-cli`
2. Manually set lower quality: `curl -X POST http://localhost:5000/api/video/quality -d '{"quality": "low"}'`
3. Increase adaptation_interval in config
4. Check signal strength if using 4G

## Security Best Practices

1. **Change default passwords** immediately after first login
2. **Use strong secret_key** - generate with `openssl rand -hex 32`
3. **Enable HTTPS** in production (use nginx reverse proxy)
4. **Limit token expiry** to reasonable time (e.g., 24 hours)
5. **Monitor active sessions** regularly
6. **Use firewall** to restrict access to necessary ports only
7. **Keep software updated** - regularly update dependencies

## Performance Optimization

### For 4G Networks

```yaml
streaming:
  initial_quality: low  # Start with low quality
  bandwidth_safety_margin: 0.6  # More conservative
```

### For Stable Networks

```yaml
streaming:
  initial_quality: high
  bandwidth_safety_margin: 0.9
  adaptation_interval: 10  # Less frequent adjustments
```

## API Reference

### Authentication Endpoints

- `POST /api/auth/login` - Login and get token
- `POST /api/auth/logout` - Logout and invalidate token
- `GET /api/auth/verify` - Verify token validity
- `POST /api/auth/change_password` - Change password

### Video Quality Endpoints

- `GET /api/video/quality` - Get current quality and stats
- `POST /api/video/quality` - Set quality manually
- `GET /api/video/stream` - MJPEG video stream (requires auth)

### System Status

- `GET /api/status` - Get full system status (requires auth)
- `GET /api/health` - Health check (no auth required)

## Support

For issues or questions:
1. Check logs for error messages
2. Verify configuration is correct
3. Test components individually
4. Consult documentation for specific components (FRP, ngrok, etc.)
