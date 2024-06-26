#!/bin/bash
# Install dependencies
cd publisher 
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install certifi
pip install --no-cache-dir -r requirements.txt

echo "Dependencies installed in publisher directory."

cd ../subscriber
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install certifi
pip install --no-cache-dir -r requirements.txt

export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

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
