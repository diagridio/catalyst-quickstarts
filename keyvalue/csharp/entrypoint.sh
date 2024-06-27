#!/bin/bash
# Create a project
echo "Creating project..."
diagrid project create kv-csharp-project-container --deploy-managed-kv

# Set this project as the default project
echo "Setting default project..."
diagrid project use kv-csharp-project-container

# Create an AppID
echo "Creating AppID..."
diagrid appid create orderapp

echo "Waiting for 30 seconds..."
sleep 30

# Connect the application to Catalyst 
echo "Starting the application..."
diagrid dev start --app-id orderapp --env PORT=5001 "dotnet run --urls=http://0.0.0.0:5001"
