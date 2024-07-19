#!/bin/bash
# Create a project and set up the environment
python3 run.py --project-name invoke-csharp-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
dotnet build

# Start the application
diagrid dev start -f "$CONFIG_FILE"
