#!/bin/bash
# Create a project
echo "Creating project..."
diagrid project create kv-javascript-project-container --deploy-managed-kv

# Set this project as the default project
echo "Setting default project..."
diagrid project use kv-javascript-project-container

# Create an AppID
echo "Creating AppID..."
diagrid appid create orderapp

echo "Waiting for 30 seconds..."
sleep 30

# Connect the application to Catalyst 
echo "Starting the application..."
diagrid dev start --app-id orderapp --env PORT=5001 "java -jar target/Main-0.0.1-SNAPSHOT.jar --port=5001"
