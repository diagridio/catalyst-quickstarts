#!/bin/bash
# Install dependencies
cd publisher 
python3 -m venv diagrid-venv
source diagrid-venv/bin/activate
pip install --upgrade pip
pip install certifi
pip install --no-cache-dir -r requirements.txt

echo "Dependencies installed in publisher directory."

cd ../subscriber
python3 -m venv diagrid-venv
source diagrid-venv/bin/activate
pip install --upgrade pip
pip install certifi
pip install --no-cache-dir -r requirements.txt

echo "Dependencies installed in subscriber directory."

cd ..

# Check if the dev file already exists and remove it if it does
if [ -f "dev-pubsub-python-project-local.yaml" ]; then
    echo "Existing dev config file found. Deleting..."
    rm "dev-pubsub-python-project-local.yaml"
fi

# Scaffold config file
diagrid dev scaffold

# Create and activate a virtual environment
python3 -m venv diagrid-venv
source diagrid-venv/bin/activate

# Install necessary packages
pip install pyyaml

# Run the Python script to update dev config file 
python3 scaffold.py
