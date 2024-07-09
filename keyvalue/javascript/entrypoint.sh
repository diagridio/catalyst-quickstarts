#!/bin/bash
# Create a project and set up the environment
python3 run.py --project-name kv-javascript-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
npm ci
echo "Dependencies installed in publisher directory."

# Start the application
diagrid dev start -f "$CONFIG_FILE"
