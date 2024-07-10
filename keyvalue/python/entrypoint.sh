#!/bin/bash
# Create a project and set up the environment
python3 run.py --project-name kv-python-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
python3 -m venv diagrid-venv
source diagrid-venv/bin/activate
pip install --upgrade pip
pip install certifi
pip install --no-cache-dir -r requirements.txt
source diagrid-venv/bin/activate
echo "Dependencies installed."

# Start the application
diagrid dev start -f "$CONFIG_FILE"
