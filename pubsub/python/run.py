import os
import subprocess
import sys
import time
import argparse

def error(message):
    print(f"Error: {message}")
    sys.exit(1)

def run_command(command, check=False):
    print(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running command: {command}")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout.strip()}")
        print(f"Stderr: {result.stderr.strip()}")
        if check:
            sys.exit(1)
        return None
    return result.stdout.strip()

def check_python_installed():
    python_check = run_command("python3 --version", check=True)
    if python_check is None:
        error("Error: Python 3.11+ must be installed to run this script.")
    
    try:
        version_str = python_check.split()[1]
        major_version, minor_version = map(int, version_str.split('.')[:2])
        if major_version < 3 or (major_version == 3 and minor_version < 11):
            error(f"Error: Python 3.11 or higher is required. Found version: {version_str}")
    except (IndexError, ValueError):
        error(f"Error: Unable to determine Python version from output: {python_check.strip()}")
    
    print(f"Python version: {version_str}")

def check_appid_status(appid_name):
    max_attempts = 5
    attempt = 1

    while attempt <= max_attempts:
        status_output = run_command(f"diagrid appid get {appid_name}")
        if status_output is None:
            error(f"Failed to get status for {appid_name}")
        
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
            error(f"Max attempts reached. {appid_name} is not ready.")
        
        print("Waiting for project subresource status to become ready...")
        time.sleep(10)
        attempt += 1

def scaffold_and_update_config(config_file):
    print("Scaffolding config file...")
    scaffold_output = run_command("diagrid dev scaffold", check=True)
    if scaffold_output is None:
        error("Failed to scaffold the config file.")

    # Create and activate a virtual environment
    env_name = "venv"
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
    prj_name = os.getenv('QUICKSTART_PROJECT_NAME')

    config_file_name = f"dev-{prj_name}.yaml"
    os.environ['CONFIG_FILE'] = config_file_name

    parser = argparse.ArgumentParser(description="Run the setup script for Diagrid projects.")
    parser.add_argument('--project-name', type=str, default=prj_name,
                        help="The name of the project to create/use.")
    parser.add_argument('--config-file', type=str, default=config_file_name,
                       help="The name of the config file to scaffold and use.")
    parser.add_argument('--is-container', action='store_true',
                        help="Flag to indicate if the script is running inside a container.")
    args = parser.parse_args()

    project_name = args.project_name
    config_file = args.config_file
    is_container = args.is_container

    print("Checking Python dependencies...")
    check_python_installed()
    
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
            error(f"Error deleting file {config_file}: {e}")

    print("Scaffolding and updating config file...")
    scaffold_and_update_config(config_file)

if __name__ == "__main__":
    main()
