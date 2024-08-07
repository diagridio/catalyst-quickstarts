#!/bin/bash
setup_venv_and_install() {
    local dir=$1
    cd $dir
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install certifi
    pip install --no-cache-dir -r requirements.txt
    echo "Dependencies installed in $dir directory."
    cd ..
}

if [ -n "$QUICKSTART_PROJECT_NAME" ]; then
  export PROJECT_NAME="$QUICKSTART_PROJECT_NAME"
  echo "Using project name: $QUICKSTART_PROJECT_NAME"
  export CONFIG_FILE="dev-$QUICKSTART_PROJECT_NAME.yaml"
  echo "Using config file: $CONFIG_FILE"
else
  echo "Error: QUICKSTART_PROJECT_NAME is not set."
  exit 1
fi

# Create a project and set up the environment
python3 run.py --project-name "$PROJECT_NAME" --config-file "$CONFIG_FILE" --is-container

# Install deps
setup_venv_and_install "publisher"
setup_venv_and_install "subscriber"

# Start the application
diagrid dev start -f "$CONFIG_FILE"
