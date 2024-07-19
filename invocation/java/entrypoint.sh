#!/bin/bash
# Create a project and set up the environment
python3 run.py --project-name invoke-java-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
cd request 
mvn clean install
echo "Dependencies installed in request directory."

cd ../reply
mvn clean install
echo "Dependencies installed in reply directory."

cd ..

# Start the application
diagrid dev start -f "$CONFIG_FILE"
