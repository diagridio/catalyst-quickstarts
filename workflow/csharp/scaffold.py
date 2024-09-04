import os
import yaml

config_file = os.getenv('CONFIG_FILE')
with open(config_file, 'r') as file:
    config_data = yaml.load(file, Loader=yaml.FullLoader)

for app in config_data['apps']:
    if app['appId'] == 'order-workflow':
        app['workDir'] = '.'
        app['command'] = ['dotnet', 'run']
        app['env']['PORT'] = 5001
        app['env']['ASPNETCORE_URLS'] = 'http://0.0.0.0:5001'

with open(config_file, 'w') as file:
    yaml.safe_dump(config_data, file, default_flow_style=False, sort_keys=False)

print("Dev config file has been updated")


