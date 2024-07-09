#!/bin/bash
chmod +x scaffold.py

# Create a project and set up the environment
python3 run.py --project-name kv-csharp-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
dotnet build
echo "Dependencies installed."

# Start the application
diagrid dev start -f "$CONFIG_FILE"
