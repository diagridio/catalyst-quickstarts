#!/bin/bash
# Create a project and set up the environment
python3 run.py --project-name pubsub-java-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
cd publisher 
mvn clean install
echo "Dependencies installed in publisher directory."

cd ../subscriber
mvn clean install
echo "Dependencies installed in subscriber directory."

cd ..

# Start the application
diagrid dev start -f "$CONFIG_FILE"
