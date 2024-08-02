import os
import yaml

config_file = os.getenv('CONFIG_FILE')
with open(config_file, 'r') as file:
    config_data = yaml.load(file, Loader=yaml.FullLoader)

for app in config_data['apps']:
    if app['appId'] == 'workflow-app':
        app['workDir'] = '.'
        app['command'] = ['java', '-jar', 'target/Main-0.0.1-SNAPSHOT.jar', '--port=5001']
        app['env']['PORT'] = 5001

with open(config_file, 'w') as file:
    yaml.safe_dump(config_data, file, default_flow_style=False, sort_keys=False)

print("YAML file has been updated.")
