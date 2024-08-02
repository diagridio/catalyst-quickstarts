#!/bin/bash
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
cd request 
mvn clean install
echo "Dependencies installed in request directory."

cd ../reply
mvn clean install
echo "Dependencies installed in reply directory."

cd ..

# Start the application
diagrid dev start -f "$CONFIG_FILE"
