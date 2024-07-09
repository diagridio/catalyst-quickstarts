#!/bin/bash
# Create a project and set up the environment
python3 run.py --project-name pubsub-javascript-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
cd publisher 
npm ci
echo "Dependencies installed in publisher directory."

cd ../subscriber
npm ci
echo "Dependencies installed in subscriber directory."

cd ..

# Start the application
diagrid dev start -f "$CONFIG_FILE"
