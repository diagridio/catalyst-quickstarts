#!/bin/bash
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

# Create a project and set up the environment
python3 run.py --project-name pubsub-python-project-container --config-file "$CONFIG_FILE" --is-container

# Install deps
setup_venv_and_install "publisher"
setup_venv_and_install "subscriber"

# Start the application
diagrid dev start -f "$CONFIG_FILE"
