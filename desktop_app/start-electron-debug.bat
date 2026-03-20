@echo off
set ELECTRON_START_URL=http://localhost:3000
set NODE_ENV=development
set ELECTRON_ENABLE_LOGGING=1
node_modules\.bin\electron.cmd main-simple.js 2>&1
pause
