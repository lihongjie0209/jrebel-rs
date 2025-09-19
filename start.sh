#!/bin/bash
# JRebel License Active Server (Rust) - Start Script

PORT=${1:-12345}
LOG_LEVEL=${2:-info}
EXPORT_SCHEMA=${3:-http}

echo "Starting JRebel License Active Server (Rust)"
echo "Port: $PORT"
echo "Log Level: $LOG_LEVEL"
echo "Schema: $EXPORT_SCHEMA"
echo

./jrebel-rs --port $PORT --log-level $LOG_LEVEL --export-schema $EXPORT_SCHEMA