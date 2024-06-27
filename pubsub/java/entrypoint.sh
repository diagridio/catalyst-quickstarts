#!/bin/bash
# Create a project
echo "Creating project..."
diagrid project create pubsub-java-project-container --deploy-managed-pubsub

# Set this project as the default project
echo "Setting default project..."
diagrid project use pubsub-java-project-container

# Create AppIDs
echo "Creating AppID..."
diagrid appid create publisher
diagrid appid create subscriber

# Create Subscription
echo "Creating Subscription..."
diagrid subscription create pubsub-subscriber --connection pubsub --topic orders --route /pubsub/neworders --scopes subscriber


echo "Waiting for 30 seconds..."
sleep 30

# Scaffold dev config file 
echo "Scaffolding dev config file..."
./scaffold.sh

# Connect the application to Catalyst 
echo "Starting the application..."
diagrid dev start
