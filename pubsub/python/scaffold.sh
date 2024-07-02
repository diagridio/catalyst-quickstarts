#!/bin/bash
# Install dependencies
setup_venv_and_install() {
    local dir=$1
    cd $dir
    python3 -m venv diagrid-venv
    source diagrid-venv/bin/activate
    pip install --upgrade pip
    pip install certifi
    pip install --no-cache-dir -r requirements.txt
    source diagrid-venv/bin/activate
    echo "Dependencies installed in $dir directory."
    cd ..
}

# Install dependencies for publisher
setup_venv_and_install "publisher"

# Install dependencies for subscriber
setup_venv_and_install "subscriber"

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
