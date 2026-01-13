#!/bin/bash

# Ensure we are in the project root
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

# Function to check if a port is in use
is_port_in_use() {
    lsof -i :$1 > /dev/null 2>&1
}

# Start Talking Head Server if not running
if ! is_port_in_use 8000; then
    echo "Starting Talking Head server (http://localhost:8000)..."
    cd talkingmodel
    python3 -m http.server 8000 &
    TM_PID=$!
    cd ..
    # Wait for server to start
    sleep 2
else
    echo "Talking Head server already running on port 8000."
fi

# Start QA App
echo "Starting QA App..."
if [ -f "venv/bin/python3" ]; then
    ./venv/bin/python3 -m qa_app.main
else
    echo "Virtual environment not found. Using system python3 (might fail if dependencies are missing)..."
    python3 -m qa_app.main
fi

# Cleanup
if [ ! -z "$TM_PID" ]; then
    echo "Stopping Talking Head server..."
    kill $TM_PID
fi
