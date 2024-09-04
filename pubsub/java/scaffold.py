import os
import yaml

config_file = os.getenv('CONFIG_FILE')

with open(config_file, 'r') as file:
    config_data = yaml.load(file, Loader=yaml.FullLoader)
    print(config_data)

for app in config_data['apps']:
    if app['appId'] == 'subscriber':
        app['appPort'] = 5002
        app['workDir'] = './subscriber'
        app['command'] = ['java', '-jar', 'target/subscriber-0.0.1-SNAPSHOT.jar', '--port=5002']
    elif app['appId'] == 'publisher':
        app['workDir'] = './publisher'
        app['command'] = ['java', '-jar', 'target/publisher-0.0.1-SNAPSHOT.jar', '--port=5001']


updated_data = {
    'project': config_data['project'],
    'apps': config_data['apps'],
    'appLogDestination': config_data.get('appLogDestination', '')
}

with open(config_file, 'w') as file:
    yaml.safe_dump(updated_data, file, default_flow_style=False, sort_keys=False)

print("Dev config file has been updated")


