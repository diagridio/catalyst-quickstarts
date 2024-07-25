#!/bin/bash
# Create a project and set up the environment
python3 run.py --project-name invoke-csharp-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
cd request 
dotnet build
echo "Dependencies installed in request directory."

cd ../reply
dotnet build
echo "Dependencies installed in reply directory."

cd ..

# Start the application
diagrid dev start -f "$CONFIG_FILE"
