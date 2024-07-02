## Catalyst Quickstarts

The Diagrid Catalyst Quickstart allows you to seamlessly create starter Catalyst resources and connect from code.

There are 2 support ways to use the quickstart: 

1. use Diagrid CLI with the quickstart command `diagrid project quickstart --type <kv | pubsub> --language <csharp | python | java | javascript>` 
2.[run the README.md of each sub directory of this repo](#howToRunREADME.md)
 

### How to run README.md

1. Install [mechanical-markdown](https://github.com/dapr/mechanical-markdown?tab=readme-ov-file#installing)

2. Authenticate with Diagrid CLI command `diagrid login`

3. Go to the directory where the README.md is, then:

**Run the quickstart in container (Recommended way)** 
  - run `mm.py README.md -t container`
  - run `docker run -v ~/.diagrid/creds:/root/.diagrid/creds -it -p 5001:5001 <image-name>` as guided in README.

**Run the quickstart locally** 
  - run `mm.py README.md -t local`
  - for Pub/Sub, run `diagrid dev start` 
  - for Key/Value Store:
    - .Net: `diagrid dev start --app-id orderapp "dotnet run --urls=http://localhost:5001"`
    - Python: `diagrid dev start --app-id orderapp "uvicorn main:app --port 5001"`
    - Javascript: `diagrid dev start --app-id orderapp --env PORT=5001 "npm run start"`
    - Java: `diagrid dev start --app-id orderapp "java -jar target/Main-0.0.1-SNAPSHOT.jar --port=5001"`
