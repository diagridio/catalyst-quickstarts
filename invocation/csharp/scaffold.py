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
        app['env']['ASPNETCORE_URLS'] = 'http://0.0.0.0:5002'
    elif app['appId'] == 'client':
        app['appPort'] = 5001
        app['workDir'] = './client'
        app['env']['ASPNETCORE_URLS'] = 'http://0.0.0.0:5001'

    app['command'] = ['dotnet', 'run']


updated_data = {
    'project': config_data['project'],
    'apps': config_data['apps'],
    'appLogDestination': config_data.get('appLogDestination', '')
}

with open(config_file, 'w') as file:
    yaml.safe_dump(updated_data, file, default_flow_style=False, sort_keys=False)

print("Dev config file has been updated")


