## Key/Value Store - Java Quickstart

It's easy to get started with Key/Value Store in Java!
With a few commands using the Diagrid CLI, you can create a new project and start developing.

This tutorial introduces how to run the Key/Value Store quickstart both locally and with Docker.


### Prerequisites
Before you proceed with the tutorial, ensure you have the appropriate prerequisites installed for the language you would like to target.

- Install [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/intro/)
- Install [Git](https://git-scm.com/downloads)
- Install latest Java 11+ [Oracle JDK](https://www.oracle.com/java/technologies/downloads/) or [Open JDK](https://jdk.java.net/)
- Install [Apache Maven 3.9.5+](https://maven.apache.org/install.html)
- Install latest [Docker](https://docs.docker.com/engine/install/)


### Run Quickstart with Docker Container

Use the Diagrid CLI to login for authentication:

```sh
diagrid login
```


<!-- STEP
name: Docker Build
tags:
  - container
-->


Build docker image, which downloads the Diagrid CLI and installs java dependencies. 

```sh
docker build -t kv-java-project-container .
```


<!-- END_STEP -->


Also, it prepares basic CLI commands to run this quickstart in `entrypoint.sh`:
- Create a project
- Set this project as the default project
- Create an AppID
- Start your application 

Run it by:
```sh
docker run -v ~/.diagrid/creds:/root/.diagrid/creds -it -p 5001:5001 kv-java-project-container
```

Then you can interact with Catalyst APIs with [this reference](https://docs.diagrid.io/catalyst/local-tutorials/key-value#interact-with-catalyst-apis)



### Run Quickstart locally

#### Log in to Diagrid Catalyst

Authenticate to your Diagrid Catalyst organization using the following command:

```sh
diagrid login
```

The Diagrid CLI is compatible with both products: Catalyst and Conductor.
If you have access to both products, If you have access to both products, you can choose which set of commands to use by specifying the product name with the command:

```sh
diagrid product use catalyst
```



To verify the current user identity and organization:
```sh
diagrid whoami
```

#### Create Catalyst Resources

##### Create Project

<!-- STEP
name: Create Catalyst Project
tags:
  - local
expected_stdout_lines:
  - "✓  Your request has been successfully submitted!"
  - "○  Check the status of your resource by running the following command:"
  - "✎  diagrid project get kv-java-project-local"
  - "○  Setting default project to kv-java-project-local"
-->


If you do not have an existing project available within your organization, create a new Catalyst project and deploy the default key/value store.
```sh
diagrid project create kv-java-project-local --deploy-managed-kv
```

<!-- END_STEP -->


<!-- STEP
name: Set Default Project
tags:
  - local
-->


To set this project as the default project in the Diagrid CLI, run:
```sh
diagrid project use kv-java-project-local
```


<!-- END_STEP -->


##### Create Application Identity
<!-- STEP
name: Create AppID 
sleep: 30
tags:
  - local
expected_stdout_lines:
  - "✓  Your request has been successfully submitted!"
  - "○  Check the status of your resource by running the following command:"
  - "✎  diagrid appid get orderapp --project kv-java-project-local"
-->


In Diagrid Catalyst, each application is represented via a corresponding remote identity, known as an App ID.
An App ID functions as the single point of contact for all interactions between a specific application and the Catalyst APIs.
Before diving into the application code, create an App ID in Diagrid Catalyst to represent the stateful order application.

```sh
diagrid appid create orderapp
```


<!-- END_STEP -->


#### Connect your applications to Catalyst


<!-- STEP
name: Install dependencies
sleep: 10
tags:
  - local
-->


Navigate to the root directory of the java app and install all dependencies.

```sh
mvn clean install
```


<!-- END_STEP -->


Run the diagrid dev start command:

```sh
diagrid dev start --app-id orderapp --env PORT=5001 "java -jar target/Main-0.0.1-SNAPSHOT.jar --port=5001"
```


Then you can interact with Catalyst APIs with [this reference](https://docs.diagrid.io/catalyst/local-tutorials/key-value#interact-with-catalyst-apis)