#!/bin/bash
# Start script for Language Tutor with PowerMem

# Set default environment variables if not set
export PYTHONUNBUFFERED=1

# Navigate to the app directory
cd "$(dirname "$0")"

echo "Starting Language Tutor with PowerMem..."

# Run the application
go run main.go
