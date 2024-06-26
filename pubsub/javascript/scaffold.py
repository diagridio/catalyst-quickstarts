import yaml

yaml_file = "dev-pubsub-javascript-project-local.yaml"

with open(yaml_file, 'r') as file:
    data = yaml.safe_load(file)

for app in data['apps']:
    if app['appId'] == 'consumer':
        app['appPort'] = 5002
        app['workDir'] = './subscriber'
        app['env']['PORT'] = 5002
    elif app['appId'] == 'publisher':
        app['appPort'] = 5001
        app['workDir'] = './publisher'
        app['env']['PORT'] = 5001

    app['command'] = ['npm', 'run', 'start']

data = {
    'project': data['project'],
    'apps': data['apps'],
    'appLogDestination': data.get('appLogDestination', '')
}

with open(yaml_file, 'w') as file:
    yaml.safe_dump(data, file, default_flow_style=False, sort_keys=False)

print("YAML file has been updated.")

