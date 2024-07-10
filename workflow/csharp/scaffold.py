import os
import yaml

config_file = os.getenv('CONFIG_FILE', 'dev-workflow-csharp-project-local.yaml')
with open(config_file, 'r') as file:
    config_data = yaml.load(file, Loader=yaml.FullLoader)

for app in config_data['apps']:
    if app['appId'] == 'workflow-app':
        app['workDir'] = '.'
        app['command'] = ['dotnet', 'run']
        app['env']['PORT'] = 5001
        app['env']['ASPNETCORE_URLS'] = 'http://localhost:5001'

with open(config_file, 'w') as file:
    yaml.safe_dump(config_data, file, default_flow_style=False, sort_keys=False)

print("YAML file has been updated.")


