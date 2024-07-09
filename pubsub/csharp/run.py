import os
import subprocess
import sys
import time
import argparse

def run_command(command, check=False):
    print(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout.strip()}")
        print(f"Stderr: {result.stderr.strip()}")
        if "resource already exists" in result.stdout.lower() or "resource already exists" in result.stderr.lower():
            print(f"Skipping error: {result.stderr.strip() or result.stdout.strip()}")
            return result.stdout.strip()
        else:
            if check:
                sys.exit(1)
            return None
    return result.stdout.strip()

def check_dotnet_installed():
    version_check = run_command("dotnet --version")
    if version_check is None:
        print("Error: .NET SDK must be installed to run this script.")
        sys.exit(1)

    try:
        version_parts = version_check.strip().split('.')
        major_version = int(version_parts[0])
        if major_version < 8:
            print(f"Error: .NET SDK version 8 or higher is required. Found version: {version_check.strip()}")
            sys.exit(1)
    except (IndexError, ValueError):
        print(f"Error: Unable to determine .NET SDK version from output: {version_check.strip()}")
        sys.exit(1)

    print(f".NET SDK version: {version_check.strip()}")

def check_appid_status(appid_name):
    max_attempts = 5
    attempt = 1

    while attempt <= max_attempts:
        status_output = run_command(f"diagrid appid get {appid_name}")
        if status_output is None:
            print(f"Failed to get status for {appid_name}")
            sys.exit(1)
        
        status_lines = status_output.split('\n')
        status = None
        for line in status_lines:
            if 'Status:' in line:
                status = line.split('Status:')[1].strip()
                break
        
        print(f"Attempt {attempt}: Current status of {appid_name}: {status}")
        if status and (status.lower() == "ready" or status.lower() == "available"):
            break
        if attempt == max_attempts:
            print(f"Max attempts reached. {appid_name} is not ready.")
            sys.exit(1)
        
        print("Waiting for 10 seconds...")
        time.sleep(10)
        attempt += 1

def scaffold_and_update_config(config_file):
    print("Scaffolding config file...")
    scaffold_output = run_command("diagrid dev scaffold", check=True)
    if scaffold_output is None:
        print("Failed to scaffold the config file.")
        sys.exit(1)

    # Create and activate a virtual environment
    env_name = "diagrid-venv"
    if os.path.exists(env_name):
        print(f"Existing virtual environment found: {env_name}")
        print(f"Deleting existing virtual environment: {env_name}")
        run_command(f"rm -rf {env_name}", check=True)

    print(f"Creating virtual environment: {env_name}")
    run_command(f"python3 -m venv {env_name}", check=True)

    print(f"Installing pyyaml in the virtual environment: {env_name}")
    run_command(f"./{env_name}/bin/pip install pyyaml", check=True)

    # Run the Python script to update the dev config file
    print("Running scaffold.py to update the dev config file...")
    run_command(f"./{env_name}/bin/python scaffold.py", check=True)

def main():
    parser = argparse.ArgumentParser(description="Run the setup script for Diagrid projects.")
    parser.add_argument('--project-name', type=str, default="pubsub-csharp-project-local",
                        help="The name of the project to create/use.")
    parser.add_argument('--config-file', type=str, default="dev-pubsub-csharp-project-local.yaml",
                        help="The name of the config file to scaffold and use.")
    parser.add_argument('--is-container', action='store_true',
                        help="Flag to indicate if the script is running inside a container.")
    args = parser.parse_args()

    project_name = args.project_name
    config_file = args.config_file
    is_container = args.is_container

    print("Checking CSharp dependencies...")
    check_dotnet_installed()
    
    print("Creating project...")
    run_command(f"diagrid project create {project_name} --deploy-managed-pubsub")

    print("Setting default project...")
    run_command(f"diagrid project use {project_name}", check=True)

    print("Creating App ID publisher and subscriber...")
    run_command("diagrid appid create publisher", check=True)
    run_command("diagrid appid create subscriber", check=True)

    print("Creating Subscription...")
    run_command("diagrid subscription create pubsub-subscriber --connection pubsub --topic orders --route /pubsub/neworders --scopes subscriber", check=True)

    print("Waiting for App ID publisher and subscriber to get ready...")
    check_appid_status("publisher")
    check_appid_status("subscriber")

    # Check if the dev file already exists and remove it if it does
    if os.path.isfile(config_file):
        print(f"Existing dev config file found: {config_file}")
        try:
            os.remove(config_file)
            print(f"Deleted existing config file: {config_file}")
        except Exception as e:
            print(f"Error deleting file {config_file}: {e}")
            sys.exit(1)

    print("Scaffolding and updating config file...")
    scaffold_and_update_config(config_file)

if __name__ == "__main__":
    main()
