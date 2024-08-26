import os
import subprocess
import sys
import time
import argparse
from yaspin import yaspin
from yaspin.spinners import Spinners

NODEJS_INSTRUCTIONS = """
Node.js and npm must be installed to run this script. Full instructions can
be found on the Node.js web site:

  https://nodejs.org/en/download
"""

def error(spinner, message):
    spinner.fail("❌")
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)

def run_command(command, check=False):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        if check:
            raise subprocess.CalledProcessError(
                result.returncode, command, output=result.stdout, stderr=result.stderr
            )
        return None

    return result.stdout.strip()


def check_js_installed():
    with yaspin(text="Checking JavaScript dependencies...") as spinner:
        node_check = run_command("node -v")
        npm_check = run_command("npm -v")
        if node_check is None or npm_check is None:
            error(spinner, NODEJS_INSTRUCTIONS)
        print(f"Node.js version: {node_check.strip()}")
        print(f"npm version: {npm_check.strip()}")
        spinner.ok("✅")

def create_project(project_name):
    with yaspin(text="") as spinner:
        try:
            run_command(f"diagrid project create {project_name} --deploy-managed-pubsub", check=True)
            spinner.ok("✅ Project created successfully")
        except subprocess.CalledProcessError as e:
            spinner.fail("❌ Failed to create project")
            print(f"Error: {e}")
            if e.output:
                print(f"{e.output}")
            if e.stderr:
                print(f"{e.stderr}")
            sys.exit(1)

def create_appid(project_name, appid_name):
    with yaspin(text="") as spinner:
        try:
            run_command(f"diagrid appid create -p {project_name} {appid_name}", check=True)
            spinner.ok(f"✅ App ID {appid_name} created successfully")
        except subprocess.CalledProcessError as e:
            spinner.fail(f"❌ Failed to create App ID {appid_name}")
            print(f"Error: {e}")
            if e.output:
                print(f"{e.output}")
            if e.stderr:
                print(f"{e.stderr}")
            sys.exit(1)


def create_subscription(project_name):
    with yaspin(text="") as spinner:
        try:
            run_command(f"diagrid subscription create pubsub-subscriber --connection pubsub --topic orders --route /pubsub/neworders --scopes subscriber --project {project_name}", check=True)
            spinner.ok("✅ Subscription created successfully")
        except subprocess.CalledProcessError as e:
            spinner.fail("❌ Failed to create subscription")
            print(f"Error: {e}")
            if e.output:
                print(f"{e.output}")
            if e.stderr:
                print(f"{e.stderr}")
            sys.exit(1)


def check_appid_status(project_name, appid_name):
    max_attempts = 8
    attempt = 1
    last_status = None

    waiting_msg = f"Waiting for App ID {appid_name} to get ready..."
    with yaspin(Spinners.dots, text=waiting_msg) as spinner:
        while attempt <= max_attempts:
            status_output = run_command(f"diagrid appid get {appid_name} -p {project_name}")

            if status_output is None:
                # Update and print the spinner text
                spinner.write(f"{waiting_msg}\n")

            else:
                status_lines = status_output.split('\n')
                status = None
                for line in status_lines:
                    if 'Status:' in line:
                        status = line.split('Status:')[1].strip()
                        last_status = status
                        break

                if status and (status.lower() == "ready" or status.lower() == "available"):
                    spinner.ok(f"✅ App ID {appid_name} is ready")
                    return 

                else:
                    # Update and print the spinner text
                    spinner.write(f"{waiting_msg}\n")

            time.sleep(10)
            attempt += 1

        spinner.fail(f"❌ Max attempts reached. {appid_name} is not ready. Final status: {last_status}")
        sys.exit(1)

def set_default_project(project_name):
    with yaspin(text="") as spinner:
        try:
            run_command(f"diagrid project use {project_name}", check=True)
            spinner.ok("✅ Default project set successfully")
        except subprocess.CalledProcessError as e:
            spinner.fail("❌ Failed to set default project")
            print(f"Error: {e}")
            if e.output:
                print(f"{e.output}")
            if e.stderr:
                print(f"{e.stderr}")
            sys.exit(1)

def scaffold_and_update_config(config_file):
    with yaspin(text="Scaffolding and updating config file...") as spinner:
        scaffold_output = run_command("diagrid dev scaffold", check=True)
        if scaffold_output is None:
            error(spinner, "Failed to scaffold the config file.")

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
        spinner.ok("✅")

def main():
    prj_name = os.getenv('QUICKSTART_PROJECT_NAME')

    config_file_name = f"dev-{prj_name}.yaml"
    os.environ['CONFIG_FILE'] = config_file_name

    parser = argparse.ArgumentParser(description="Run the setup script for Diagrid projects.")
    parser.add_argument('--project-name', type=str, default=prj_name,
                        help="The name of the project to create/use.")
    parser.add_argument('--config-file', type=str, default=config_file_name,
                       help="The name of the config file to scaffold and use.")
    args = parser.parse_args()

    project_name = args.project_name
    config_file = args.config_file

    check_js_installed()
    
    print("Creating project...")
    create_project(prj_name)

    print("Creating App ID publisher...")
    create_appid(prj_name, "publisher")
    print("Creating App ID subscriber...")
    create_appid(prj_name, "subscriber")

    print("Creating subscription...")
    create_subscription(prj_name)

    check_appid_status(project_name, "publisher")
    check_appid_status(project_name, "subscriber")

    print("Setting default project...")
    set_default_project(prj_name)

    # Check if the dev file already exists and remove it if it does
    if os.path.isfile(config_file):
        print(f"Existing dev config file found: {config_file}")
        try:
            os.remove(config_file)
            print(f"Deleted existing config file: {config_file}")
        except Exception as e:
            with yaspin(text=f"Error deleting file {config_file}") as spinner:
                error(spinner, f"Error deleting file {config_file}: {e}")

    scaffold_and_update_config(config_file)




if __name__ == "__main__":
    main()
