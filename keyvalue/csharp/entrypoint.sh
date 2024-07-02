#!/bin/bash
check_appid_status() {
    local appid_name=$1
    local max_attempts=5
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        status=$(diagrid appid get $appid_name | grep 'Status:' | awk '{print $2}')
        echo "Attempt $attempt: Current status of $appid_name: $status"
        if [ "$status" == "ready" ]; then
            break
        fi
        if [ $attempt -eq $max_attempts ]; then
            echo "Max attempts reached. $appid_name is not ready."
            exit 1
        fi
        echo "Waiting for 10 seconds..."
        sleep 10
        attempt=$((attempt + 1))
    done
}
# Create a project
echo "Creating project..."
diagrid project create kv-csharp-project-container --deploy-managed-kv

# Set this project as the default project
echo "Setting default project..."
diagrid project use kv-csharp-project-container

# Create an AppID
echo "Creating App ID orderapp..."
diagrid appid create orderapp

echo "Waiting for App ID orderapp to become ready..."
check_appid_status orderapp

# Connect the application to Catalyst 
echo "Starting the application..."
diagrid dev start --app-id orderapp --env PORT=5001 "dotnet run --urls=http://0.0.0.0:5001"
