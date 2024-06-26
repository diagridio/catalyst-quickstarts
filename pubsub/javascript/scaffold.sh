#!/bin/bash
# Install dependencies
cd publisher 
npm ci
echo "Dependencies installed in publisher directory."

cd ../subscriber
npm ci
echo "Dependencies installed in subscriber directory."

cd ..

# Scaffold config file
diagrid dev scaffold

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install necessary packages
pip install pyyaml

# Run the Python script to update dev config file 
python scaffold.py
