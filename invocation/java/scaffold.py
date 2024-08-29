import os
import yaml

config_file = os.getenv('CONFIG_FILE')

with open(config_file, 'r') as file:
    config_data = yaml.load(file, Loader=yaml.FullLoader)
    print(config_data)

for app in config_data['apps']:
    if app['appId'] == 'server':
        app['appPort'] = 5002
        app['workDir'] = './server'
        app['command'] = ['java', '-jar', 'target/server-0.0.1-SNAPSHOT.jar', '--port=5002']
    elif app['appId'] == 'client':
        app['appPort'] = 5001
        app['workDir'] = './client'
        app['command'] = ['java', '-jar', 'target/client-0.0.1-SNAPSHOT.jar', '--port=5001']


updated_data = {
    'project': config_data['project'],
    'apps': config_data['apps'],
    'appLogDestination': config_data.get('appLogDestination', '')
}

with open(config_file, 'w') as file:
    yaml.safe_dump(updated_data, file, default_flow_style=False, sort_keys=False)

print("Dev config file has been updated")


