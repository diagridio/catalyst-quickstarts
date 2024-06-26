## Catalyst Quickstarts

The Diagrid Catalyst Quickstart allows you to more easily create starter Catalyst resources and connect from code.

There are 2 support ways to use the quickstart: 

1. use Diagrid CLI with the quickstart command `diagrid project quickstart --type <kv | pubsub> --language <csharp | python | java | javascript>` 
2. run the README.md of each sub directory of this repo
 

### How to run README.md

1. Install [mechanical-markdown](https://github.com/dapr/mechanical-markdown?tab=readme-ov-file#installing)

2. Authenticate with Diagrid CLI command `diagrid login`

3. Go to the directory where the README.md is, then:

**Run the quickstart in container (Recommended way)** 
  - run `mm.py README.md -t container`
  - run `docker run -v ~/.diagrid/creds:/root/.diagrid/creds -it -p 5001:5001 <image-name>` as guided in README.

**Run the quickstart locally** 
  - run `mm.py README.md -t local`
  - run `diagrid dev start` for Pub/Sub, or `diagrid dev start --app-id orderapp "uvicorn main:app --port 5001"` for Key/Value Store




