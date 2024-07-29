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
        app['command'] = ['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '5002']
    elif app['appId'] == 'publisher':
        app['appPort'] = 5001
        app['workDir'] = './publisher'
        app['command'] = ['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '5001']


updated_data = {
    'project': config_data['project'],
    'apps': config_data['apps'],
    'appLogDestination': config_data.get('appLogDestination', '')
}

with open(config_file, 'w') as file:
    yaml.safe_dump(updated_data, file, default_flow_style=False, sort_keys=False)

print("YAML file has been updated.")


