#!/bin/bash
if [ -n "$QUICKSTART_PROJECT_NAME" ]; then
  export CONFIG_FILE="dev-$QUICKSTART_PROJECT_NAME.yaml"
else
  echo "Error: QUICKSTART_PROJECT_NAME is not set."
  exit 1
fi

echo "Using config file: $CONFIG_FILE"

if [ -n "$QUICKSTART_PROJECT_NAME" ]; then
  export PROJECT_NAME="$QUICKSTART_PROJECT_NAME"
else
  echo "Error: QUICKSTART_PROJECT_NAME is not set."
  exit 1
fi

echo "Using project name: $QUICKSTART_PROJECT_NAME"

# Create a project and set up the environment
python3 run.py --project-name "$PROJECT_NAME" --config-file "$CONFIG_FILE" --is-container

# Install deps
cd publisher 
mvn clean install
echo "Dependencies installed in publisher directory."

cd ../subscriber
mvn clean install
echo "Dependencies installed in subscriber directory."

cd ..

# Start the application
diagrid dev start -f "$CONFIG_FILE"
