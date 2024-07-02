## Publish/Subscribe - .Net Quickstart

It's easy to get started with Pub/Sub in .Net!
With a few commands using the Diagrid CLI, you can create a new project and start developing.

This tutorial introduces how to run the Pub/Sub quickstart both locally and with Docker.


### Prerequisites
Before you proceed with the tutorial, ensure you have the appropriate prerequisites installed for the language you would like to target.

- Install [Diagrid CLI](https://docs.diagrid.io/catalyst/references/cli-reference/intro/)
- Install [Git](https://git-scm.com/downloads)
- Install latest [.Net 8+ SDK](https://dotnet.microsoft.com/en-us/download)
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


Build docker image, which downloads the Diagrid CLI and installs .Net dependencies. 

```sh
docker build -t pubsub-csharp-project-container .
```


<!-- END_STEP -->


Also, it prepares basic CLI commands to run this quickstart in `entrypoint.sh`:
- Create a project
- Set this project as the default project
- Create 2 App ID: publisher and subscriber
- Create a subscription
- Start your application 

Run it by:
```sh
docker run -v ~/.diagrid/creds:/root/.diagrid/creds -it -p 5001:5001 pubsub-csharp-project-container
```

Then you can interact with Catalyst APIs with [this local tutorial](https://docs.diagrid.io/catalyst/local-tutorials/publish-subscribe#interact-with-catalyst-apis)



### Run Quickstart locally

#### Log in to Diagrid Catalyst

Authenticate to your Diagrid Catalyst organization using the following command:

```sh
diagrid login
```

The Diagrid CLI is compatible with both products: Catalyst and Conductor.
If you have access to both products, then you can choose which set of commands to use by specifying the product name with the command:

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
  - "✎  diagrid project get pubsub-csharp-project-local"
  - "○  Setting default project to pubsub-csharp-project-local"
-->


If you do not have an existing project available within your organization, create a new Catalyst project and deploy the default key/value store.
```sh
diagrid project create pubsub-csharp-project-local --deploy-managed-pubsub
```

<!-- END_STEP -->


<!-- STEP
name: Set Default Project
tags:
  - local
-->


To set this project as the default project in the Diagrid CLI, run:
```sh
diagrid project use pubsub-csharp-project-local
```


<!-- END_STEP -->


##### Create Application Identity
<!-- STEP
name: Create App ID 
sleep: 30
tags:
  - local
expected_stdout_lines:
  - "✓  Your request has been successfully submitted!"
  - "○  Check the status of your resource by running the following command:"
  - "✎  diagrid appid get publisher --project pubsub-csharp-project-local"
  - "✓  Your request has been successfully submitted!"
  - "○  Check the status of your resource by running the following command:"
  - "✎  diagrid appid get subscriber --project pubsub-csharp-project-local"
-->

In Diagrid Catalyst, each application is represented by a remote identity, known as an App ID.
An App ID functions as the single point of contact for all interactions between an application and the Catalyst APIs.
Before diving into the application code, create two App IDs in Diagrid Catalyst, one to represent the publishing app, and one to represent the subscribing app.

```sh
diagrid appid create publisher
diagrid appid create subscriber
```


<!-- END_STEP -->

##### Create Pub/Sub Topic Subscription
<!-- STEP
name: Create Subscription 
sleep: 20
tags:
  - local
expected_stdout_lines:
  - "✓  Your request has been successfully submitted!"
-->

With the Diagrid Pub/Sub Broker already provisioned in your project, the next step is to create a topic subscription through which the subscriber App ID can subscribe to messages sent by the publisher.

Use the following command to ensure all messages sent to the orders topic in the message broker are routed to the /pubsub/neworders endpoint of the subscriber application:

```sh
diagrid subscription create pubsub-subscriber --connection pubsub --topic orders --route /pubsub/neworders --scopes subscriber
```


<!-- END_STEP -->


#### Connect your applications to Catalyst

<!-- STEP
name: Scaffold Dev Config
sleep: 5
tags:
  - local
-->


Install the dependencies and set up your local Catalyst development environment by running the following :

```sh
chmod +x scaffold.sh
./scaffold.sh
```

This script needs Python installed, if you don't have the environment, you can also finish this step manually by following the [tutorial](https://docs.diagrid.io/catalyst/local-tutorials/publish-subscribe#connect-your-applications-to-catalyst)

<!-- END_STEP -->


Then run your applications and connect the subscriber App ID to the local subscriber app using the following command:
```sh
diagrid dev start 
```


Then you can interact with Catalyst APIs with [this local tutorial](https://docs.diagrid.io/catalyst/local-tutorials/publish-subscribe#interact-with-catalyst-apis)
