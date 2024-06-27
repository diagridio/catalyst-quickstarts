#!/bin/bash
# Install dependencies
cd publisher 
mvn clean install
echo "Dependencies installed in publisher directory."

cd ../subscriber
mvn clean install
echo "Dependencies installed in subscriber directory."

cd ..

# Check if the dev file already exists and remove it if it does
if [ -f "dev-pubsub-java-project-local.yaml" ]; then
    echo "Existing dev config file found. Deleting..."
    rm "dev-pubsub-java-project-local.yaml"
fi


# Scaffold config file
diagrid dev scaffold

# Ensure the virtual environment directory is clear before creating a new one
if [ -d "venv" ]; then
    rm -rf venv
fi

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install necessary packages
pip install pyyaml

# Run the Python script to update dev config file 
python scaffold.py

