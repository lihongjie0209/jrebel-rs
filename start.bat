@echo off
rem JRebel License Active Server (Rust) - Start Script

set PORT=12345
set LOG_LEVEL=info
set EXPORT_SCHEMA=http

if "%1" neq "" set PORT=%1
if "%2" neq "" set LOG_LEVEL=%2
if "%3" neq "" set EXPORT_SCHEMA=%3

echo Starting JRebel License Active Server (Rust)
echo Port: %PORT%
echo Log Level: %LOG_LEVEL%
echo Schema: %EXPORT_SCHEMA%
echo.

jrebel-rs.exe --port %PORT% --log-level %LOG_LEVEL% --export-schema %EXPORT_SCHEMA%

pause