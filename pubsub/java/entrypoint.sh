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
diagrid project create pubsub-java-project-container --deploy-managed-pubsub

# Set this project as the default project
echo "Setting default project..."
diagrid project use pubsub-java-project-container

# Create AppIDs
echo "Creating App ID publisher and subscriber..."
diagrid appid create publisher
diagrid appid create subscriber

# Create Subscription
echo "Creating Subscription..."
diagrid subscription create pubsub-subscriber --connection pubsub --topic orders --route /pubsub/neworders --scopes subscriber


echo "Wating for App ID publisher and subscriber get ready..."
check_appid_status publisher
check_appid_status subscriber

# Scaffold dev config file 
echo "Scaffolding dev config file..."
./scaffold.sh

# Connect the application to Catalyst 
echo "Starting the application..."
diagrid dev start -f "$CONFIG_FILE"
