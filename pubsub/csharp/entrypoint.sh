#!/bin/bash
# Create a project and set up the environment
python3 run.py --project-name pubsub-csharp-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
cd publisher 
dotnet build
echo "Dependencies installed in publisher directory."

cd ../subscriber
dotnet build
echo "Dependencies installed in subscriber directory."

cd ..

# Start the application
diagrid dev start -f "$CONFIG_FILE"
