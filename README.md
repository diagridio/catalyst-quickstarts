## Catalyst Quickstarts

The Diagrid Catalyst Quickstart allows you to seamlessly create starter Catalyst resources and connect from code.

There are 2 support ways to use the quickstart: 

**Run the quickstart in container**
1. install Docker
2. run `diagrid project quickstart --type <kv|pubsub> --language <csharp|java|javascript|python> --container`

The container will set up all dev env and dependencies for you.

**Run the quickstart on host** 
1. run `diagrid project quickstart --type <kv|pubsub> --language <csharp|java|javascript|python>`
2. follow the instructions to install dependencies and run `diagrid dev start -f <dev config file>`

This requires the user to have corresponding dev env on the host.
