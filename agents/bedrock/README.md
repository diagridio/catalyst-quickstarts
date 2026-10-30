# Strands Agent on Amazon Bedrock AgentCore - Budget Analyst

This quickstart deploys the [Strands Budget Analyst](../strands/) to [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html), with Catalyst running each agent run as a durable Dapr Workflow. AgentCore hosts the container and its sessions. Catalyst stores the workflow state and the agent registry, so a run's progress and result are not lost when an AgentCore session ends.

## What This Quickstart Demonstrates

- **Strands on AgentCore**: The agent serves the AgentCore Runtime HTTP contract, `POST /invocations` and `GET /ping` on port 8080
- **Durable runs from a serverless host**: The container connects to Catalyst over the internet. There is no Dapr sidecar to run
- **Credentials kept out of the runtime definition**: The Catalyst App ID token and the OpenAI key live in AWS Secrets Manager. Only the container's execution role can read them
- **Same code locally and on AWS**: `diagrid dev run` runs the same `main.py` before you deploy it

## How the Code Is Organized

- `main.py` holds what is specific to this agent: its tool, its model and its prompt. It builds the Strands `DaprWorkflowAgentRunner` as any Catalyst agent does, passes it to `BedrockRunner`, and calls `runner.serve()`.
- `bedrock_runner.py` holds what AgentCore needs. `BedrockRunner` takes the agent's workflow runner and serves it on `POST /invocations` and `GET /ping`, port 8080. What it needs to know about the framework, such as where a run stores its task and its answer, is in an adapter for that runner type. Only Strands has one (`StrandsAdapter`). Another framework's runner, such as LangGraph's, needs its own adapter in `ADAPTERS`. Importing the module loads the secrets, so `main.py` imports it before anything that imports the Dapr SDK.

## How the Agent Connects to Catalyst

The agent reads these variables. Locally, `diagrid dev run` sets the three Catalyst ones and you set the model ones:

| Variable | What it is | Where it is kept on AgentCore |
|----------|------------|-------------------------------|
| `DAPR_GRPC_ENDPOINT` | The project's gRPC endpoint | Runtime environment variable. It is not a secret |
| `DAPR_HTTP_ENDPOINT` | The project's HTTP endpoint | Runtime environment variable. It is not a secret |
| `DAPR_API_TOKEN` | The token of the `budget-planner` App ID | Secrets Manager |
| `OPENAI_API_KEY` | The API key of your model provider | Secrets Manager |
| `OPENAI_BASE_URL` | The provider's OpenAI-compatible endpoint. Defaults to `https://api.openai.com/v1` | Runtime environment variable. It is not a secret |
| `OPENAI_MODEL` | A model the provider serves. Defaults to `gpt-4o-mini` | Runtime environment variable. It is not a secret |
To use another OpenAI-compatible provider, set `OPENAI_BASE_URL` to its endpoint, `OPENAI_MODEL` to one of its models, and `OPENAI_API_KEY` to its key. The model must support tool calling, because the agent calls `calculate_budget`.

The runtime gets a single environment variable that points at the secret, `AGENT_SECRET_ARN`. At startup, `bedrock_runner.py` reads the secret with the runtime's execution role and loads its keys into the environment. It does this before the Dapr SDK is imported, because the SDK reads its variables on import. The execution role may read that one secret and nothing else, and the secret values never appear in the runtime definition, in the AgentCore console or in the CLI history.

Your Diagrid API key (`DIAGRID_API_KEY`) stays with you or your CI pipeline. You use it to create the Catalyst resources and to read the App ID token. The container does not need it: the App ID token can only act as `budget-planner` in this one project, while an API key can manage the project.

## Prerequisites

1. A [Diagrid Catalyst account](https://catalyst.diagrid.io/)
2. [Diagrid CLI](https://docs.diagrid.io/getting-started/install-cli) installed
3. [Python 3.11–3.13](https://www.python.org/downloads/)
4. [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
5. An [OpenAI API key](https://platform.openai.com/api-keys), or a key for another provider with an OpenAI-compatible API
6. An AWS account in a [region where AgentCore is available](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html), and the [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) logged in to it
7. An Amazon ECR repository. [AgentCore Runtime requires](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html#bedrock-agentcore-runtime-requirements) the image to be in ECR
8. [Docker](https://docs.docker.com/get-docker/) with `buildx`. AgentCore Runtime runs only `linux/arm64` images
9. [jq](https://jqlang.org/download/)

## Setup

Navigate to the `bedrock` directory and install the dependencies using `uv`:

```bash
cd agents/bedrock
uv sync
```

Set the values the steps below use. Replace the placeholders with your own:

```bash
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ECR_REPO_NAME="budget-planner"
export ECR_REPO="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME"
export OPENAI_API_KEY="your-key-here"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o-mini"
```

## 1. Create the Catalyst Resources

1. Log in to Catalyst. Interactively:

```bash
diagrid login
```

Or, in a CI pipeline, with a Diagrid API key:

```bash
diagrid login --api-key "$DIAGRID_API_KEY"
```

To create a key for a pipeline, run `diagrid apikey create --name budget-planner-deploy --role cra.diagrid:editor --duration 86400` once you are logged in. The `--duration` makes the key expire after a day.

2. Create a Catalyst project for the quickstart and use it as the default project for the current session:

```bash
diagrid project create bedrock-quickstart --enable-managed-workflow --deploy-managed-kv --wait --use
```

3. Create an agent for the project. This also creates the `budget-planner` App ID that the container connects as:

```bash
diagrid agent create budget-planner --wait
```

## 2. Run Locally

Run the same code with Catalyst before you deploy it:

```bash
uv run diagrid dev run -f dev-python-bedrock.yaml --approve
```

Wait until the output shows `Uvicorn running on http://0.0.0.0:8080`. From another terminal, send the request AgentCore will send:

```bash
curl -i -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: local-session-0123456789abcdef0123" \
  -d '{"task": "Calculate the budget for a corporate event with venue, catering, and entertainment"}'
```

Or open [`test.http`](./test.http) in VS Code with the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) extension. Stop the app with `Ctrl+C` before you go on.

## 3. Read the Catalyst Connection Values

```bash
export DAPR_GRPC_ENDPOINT="$(diagrid project get bedrock-quickstart -o json | jq -r .status.endpoints.grpc.url)"
export DAPR_HTTP_ENDPOINT="$(diagrid project get bedrock-quickstart -o json | jq -r .status.endpoints.http.url)"
export DAPR_API_TOKEN="$(diagrid appid get budget-planner -o json | jq -r .status.apiToken)"
```

## 4. Build and Push the Image

If you do not have an ECR repository yet, create one:

```bash
aws ecr create-repository --repository-name "$ECR_REPO_NAME" --region "$AWS_REGION"
```

Log in to ECR:

```bash
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```

Then build for `linux/arm64` and push. `docker buildx create --use` is needed once, so `buildx` can build for another architecture. Tag the image with the current git commit, so that each runtime version points to the code it was built from:

```bash
export IMAGE_TAG="$(git rev-parse --short HEAD)"
docker buildx create --use
docker buildx build --platform linux/arm64 -t "$ECR_REPO:$IMAGE_TAG" --push .
```

To check the image before you deploy it, run it with the values from step 3. `-e NAME` with no value copies the variable from your shell, so the secrets do not appear on the command line:

```bash
docker run --rm --platform linux/arm64 -p 8080:8080 \
  -e DAPR_GRPC_ENDPOINT -e DAPR_HTTP_ENDPOINT -e DAPR_API_TOKEN \
  -e OPENAI_API_KEY -e OPENAI_BASE_URL -e OPENAI_MODEL \
  "$ECR_REPO:$IMAGE_TAG"
```

Then send the `curl` request from step 2.

## 5. Store the Secrets

Store the App ID token and the OpenAI key as one JSON secret. This follows the [Secrets Manager guidance for the AWS CLI](https://docs.aws.amazon.com/secretsmanager/latest/userguide/security_cli-exposure-risks.html): the values go into a file only you can read, the CLI reads that file, and the file is destroyed. Neither value appears in your shell history or on a command line:

```bash
(umask 077 && jq -n --arg token "$DAPR_API_TOKEN" --arg openai "$OPENAI_API_KEY" \
  '{DAPR_API_TOKEN: $token, OPENAI_API_KEY: $openai}' > secret.json)
aws secretsmanager create-secret --name budget-planner/agentcore \
  --secret-string file://secret.json
shred -u secret.json
export AGENT_SECRET_ARN="$(aws secretsmanager describe-secret --secret-id budget-planner/agentcore --query ARN --output text)"
```

If `shred` is not installed, delete the file with `rm secret.json`.

## 6. Create the Execution Role

AgentCore runs the container with this role. The trust policy and the permissions are the [AgentCore Runtime execution role](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html#runtime-permissions-execution-role) from the AWS docs, with three changes:

- ECR access is limited to your one repository.
- The agent may read its one secret.
- Two statements are left out. Bedrock model invocation is not needed, because the agent calls OpenAI. Workload access tokens are not needed, because the agent does not use AgentCore Identity.

```bash
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AssumeRolePolicy",
    "Effect": "Allow",
    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {"aws:SourceAccount": "$AWS_ACCOUNT_ID"},
      "ArnLike": {"aws:SourceArn": "arn:aws:bedrock-agentcore:$AWS_REGION:$AWS_ACCOUNT_ID:*"}
    }
  }]
}
EOF

cat > permissions.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRImageAccess",
      "Effect": "Allow",
      "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
      "Resource": "arn:aws:ecr:$AWS_REGION:$AWS_ACCOUNT_ID:repository/$ECR_REPO_NAME"
    },
    {
      "Sid": "ECRTokenAccess",
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
      "Resource": "arn:aws:logs:$AWS_REGION:$AWS_ACCOUNT_ID:log-group:/aws/bedrock-agentcore/runtimes/*"
    },
    {
      "Effect": "Allow",
      "Action": "logs:PutResourcePolicy",
      "Resource": "arn:aws:logs:$AWS_REGION:$AWS_ACCOUNT_ID:log-group:/aws/bedrock-agentcore/runtimes/budget_planner-*"
    },
    {
      "Effect": "Allow",
      "Action": "logs:DescribeLogGroups",
      "Resource": "arn:aws:logs:$AWS_REGION:$AWS_ACCOUNT_ID:log-group:*"
    },
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:$AWS_REGION:$AWS_ACCOUNT_ID:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
    },
    {
      "Effect": "Allow",
      "Action": ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": "cloudwatch:PutMetricData",
      "Resource": "*",
      "Condition": {"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}}
    },
    {
      "Sid": "ReadAgentSecret",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "$AGENT_SECRET_ARN"
    }
  ]
}
EOF

aws iam create-role --role-name budget-planner-agentcore \
  --assume-role-policy-document file://trust-policy.json
aws iam put-role-policy --role-name budget-planner-agentcore \
  --policy-name budget-planner-agentcore --policy-document file://permissions.json
export ROLE_ARN="$(aws iam get-role --role-name budget-planner-agentcore --query Role.Arn --output text)"
```

If you switch the agent to a Bedrock model, add the `BedrockModelInvocation` statement from the AWS docs.

## 7. Create the Agent Runtime

The runtime uses the `PUBLIC` network mode, because the container connects out to Catalyst and to the model provider. Only the endpoints, the model name and the secret ARN go into the runtime definition. The runtime name may contain only letters, digits and underscores:

```bash
aws bedrock-agentcore-control create-agent-runtime \
  --region "$AWS_REGION" \
  --agent-runtime-name budget_planner \
  --agent-runtime-artifact "$(jq -n --arg uri "$ECR_REPO:$IMAGE_TAG" '{containerConfiguration: {containerUri: $uri}}')" \
  --network-configuration networkMode=PUBLIC \
  --role-arn "$ROLE_ARN" \
  --environment-variables "$(jq -n \
      --arg grpc "$DAPR_GRPC_ENDPOINT" --arg http "$DAPR_HTTP_ENDPOINT" --arg secret "$AGENT_SECRET_ARN" \
      --arg base_url "$OPENAI_BASE_URL" --arg model "$OPENAI_MODEL" \
      '{DAPR_GRPC_ENDPOINT: $grpc, DAPR_HTTP_ENDPOINT: $http, AGENT_SECRET_ARN: $secret,
        OPENAI_BASE_URL: $base_url, OPENAI_MODEL: $model}')"
```

Look up the runtime's ARN by its name, and wait until the runtime is `READY`. Run the lookup again in any new shell before the steps below:

```bash
export RUNTIME_ARN="$(aws bedrock-agentcore-control list-agent-runtimes --region "$AWS_REGION" \
  --query "agentRuntimes[?agentRuntimeName=='budget_planner'].agentRuntimeArn | [0]" --output text)"
echo "$RUNTIME_ARN"
aws bedrock-agentcore-control get-agent-runtime --region "$AWS_REGION" \
  --agent-runtime-id "${RUNTIME_ARN##*/}" --query status --output text
```

`echo` must print an ARN that starts with `arn:aws:bedrock-agentcore:`. An empty `RUNTIME_ARN` makes the invoke below fail with `404 UnknownOperationException`.

## 8. Invoke the Agent

A session runs one task at a time, and the workflow instance ID is the session ID. The agent does not read the payload's fields: the whole payload is the task. Every request waits until the run ends:

| Request | Answer |
|---------|--------|
| No run in progress | `200` with the result, once the run ends |
| A run in progress | `409`. The task is not started |

Dapr refuses to start a workflow whose instance ID is still running, which is how a second task is detected. AgentCore [returns a container's 4xx or 5xx answer to the caller](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html#http-error-handling) as a `424 RuntimeClientError`, so `409` and `500` reach the AWS CLI as that error.

The runtime session ID must be at least 33 characters long. Invocations with the same session ID go to the same AgentCore session, and they share one conversation, so a task can follow up on an earlier one. See [Conversation History](#conversation-history).

The response has the workflow `instance_id`, its `status` and the agent's `result`.


```bash
export SESSION_ID="budget-planner-$(uuidgen)"
aws bedrock-agentcore invoke-agent-runtime \
  --region "$AWS_REGION" \
  --agent-runtime-arn "$RUNTIME_ARN" \
  --runtime-session-id "$SESSION_ID" \
  --content-type application/json \
  --accept application/json \
  --cli-binary-format raw-in-base64-out \
  --payload '{"task": "Calculate the budget for a corporate event with venue, catering, and entertainment"}' \
  response.json && jq . response.json

{
    "runtimeSessionId": "budget-planner-50e0376b-0d63-438d-bb5d-e6c44f6360a1",
    "contentType": "application/json",
    "statusCode": 200
}
{
  "instance_id": "budget-planner-50e0376b-0d63-438d-bb5d-e6c44f6360a1",
  "status": "COMPLETED",
  "result": "Here's the budget breakdown for your corporate event:\n\n- **Venue**: $3,500\n- **Catering**: $2,250\n- **Entertainment**: $1,500\n\n**Total**: $7,250  \n**Recommended buffer (15%)**: $1,088  \n**Grand Total**: $8,338\n\nLet me know if you need any further assistance!"
}
```

Continue the conversation using the same session id:

```bash
aws bedrock-agentcore invoke-agent-runtime \
  --region "$AWS_REGION" \
  --agent-runtime-arn "$RUNTIME_ARN" \
  --runtime-session-id "$SESSION_ID" \
  --content-type application/json \
  --accept application/json \
  --cli-binary-format raw-in-base64-out \
  --payload '{"task": "Recalculate without entertainment"}' \
  response.json && jq . response.json

{
    "runtimeSessionId": "budget-planner-50e0376b-0d63-438d-bb5d-e6c44f6360a1",
    "contentType": "application/json",
    "statusCode": 200
}
{
  "instance_id": "budget-planner-50e0376b-0d63-438d-bb5d-e6c44f6360a1",
  "status": "COMPLETED",
  "result": "Here's the updated budget breakdown for your corporate event without entertainment:\n\n- **Venue**: $3,500  \n- **Catering**: $2,250  \n\n**Total**: $5,750  \n**Recommended buffer (15%)**: $862  \n**Grand Total**: $6,612  \n\nIf you need anything else, feel free to ask!"
}
```

## 9. Inspect the Run in Catalyst

Open the [Catalyst dashboard](https://catalyst.diagrid.io/agents) and navigate to Agents > budget-planner. Select the most recent run to see each model call and tool call the workflow recorded.

## Conversation History

Tasks sent with the same session ID share one conversation. The agent carries it in the task text. Before starting a task, it reads the session's last run from Catalyst, which is the workflow instance named after the session ID. That run's task is already the conversation up to that run, written as lines starting with `User:` and `Assistant:`. The agent adds that run's answer and the new request to it, and starts the new run with the result. The system prompt tells the model to answer the last `User:` line. Because each run's task holds the whole conversation, and Catalyst stores it with the run, the history survives a crash or a new container without a separate store.

What the model sees:

- The history as one block of text, not as separate turns.
- Earlier requests and answers, without the tool calls and tool results of earlier tasks.
- At most the newest 20,000 characters of the conversation (`MAX_HISTORY_CHARS` in `bedrock_runner.py`).

## Update the Image

Pushing a new image does not change the runtime. [Each update to the runtime creates a new version](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html), and the `DEFAULT` endpoint that `invoke-agent-runtime` uses moves to it. A session that started before the update keeps running the version it started with, so invoke with a new `SESSION_ID` to reach the new image.

Commit your changes first: the tag is the commit, so building again without a new commit reuses the previous tag. Then build and push the new image. The ECR login from step 4 is [valid for 12 hours](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html), so log in again if it has expired:


Log in to ECR:

```bash
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```

```bash
export IMAGE_TAG="$(git rev-parse --short HEAD)"
docker buildx build --platform linux/arm64 -t "$ECR_REPO:$IMAGE_TAG" --push .
```

An update replaces the runtime's whole configuration: any setting you leave out is removed from the new version. So pass the same parameters as in step 7, with the new image:

```bash
export RUNTIME_ID="${RUNTIME_ARN##*/}"
aws bedrock-agentcore-control update-agent-runtime --region "$AWS_REGION" \
  --agent-runtime-id "$RUNTIME_ID" \
  --agent-runtime-artifact "$(jq -n --arg uri "$ECR_REPO:$IMAGE_TAG" '{containerConfiguration: {containerUri: $uri}}')" \
  --network-configuration networkMode=PUBLIC \
  --role-arn "$ROLE_ARN" \
  --environment-variables "$(jq -n \
      --arg grpc "$DAPR_GRPC_ENDPOINT" --arg http "$DAPR_HTTP_ENDPOINT" --arg secret "$AGENT_SECRET_ARN" \
      --arg base_url "$OPENAI_BASE_URL" --arg model "$OPENAI_MODEL" \
      '{DAPR_GRPC_ENDPOINT: $grpc, DAPR_HTTP_ENDPOINT: $http, AGENT_SECRET_ARN: $secret,
        OPENAI_BASE_URL: $base_url, OPENAI_MODEL: $model}')"
```

Wait until the runtime is `READY`, then check that the new version has the new image and the same environment variables:

```bash
aws bedrock-agentcore-control get-agent-runtime --region "$AWS_REGION" --agent-runtime-id "$RUNTIME_ID" \
  --query '{status: status, version: agentRuntimeVersion, image: agentRuntimeArtifact.containerConfiguration.containerUri, env: environmentVariables}'
```

## Rotate the Credentials

The container reads the secret when an AgentCore session starts. To rotate the App ID token or the OpenAI key, update the secret. Sessions that start after the update use the new values:

```bash
(umask 077 && jq -n --arg token "$DAPR_API_TOKEN" --arg openai "$OPENAI_API_KEY" \
  '{DAPR_API_TOKEN: $token, OPENAI_API_KEY: $openai}' > secret.json)
aws secretsmanager put-secret-value --secret-id "$AGENT_SECRET_ARN" \
  --secret-string file://secret.json
shred -u secret.json
```

## Good to Know

- **The workflow worker runs only while an AgentCore session is running.** Each session runs in its own microVM, and each microVM's container connects to Catalyst as a worker for `budget-planner`. AgentCore [stops a session](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html#session-lifecycle) after 15 minutes without activity, or 8 hours after it started, by default. While the session's workflow is running, `/ping` answers [`HealthyBusy`](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-http-protocol-contract.html#ping-endpoint), which AgentCore counts as activity, so the idle timeout does not stop a run even when no request is waiting for it. The 8-hour limit still applies. A run that is interrupted keeps its state in Catalyst. It resumes when the next invocation starts a container, not before.
- **`/invocations` waits for the run to finish.** AgentCore [allows a synchronous request 15 minutes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html#invocation-limits), and the limit cannot be raised. A run that takes longer keeps running in Catalyst, but the caller gets no answer. The result is in the run's output in Catalyst.
- **There is no pub/sub subscription.** The [Strands quickstart](../strands/) receives tasks from a topic, which Catalyst delivers by calling the app. An AgentCore container has no address Catalyst can call, so this agent receives tasks only through `/invocations`.
- **The diagrid SDK sends one anonymous usage event per process.** On AgentCore that is one event for each session's container. It holds versions, the platform and the agent framework, and no prompts, app IDs or hostnames. To turn it off, add `DO_NOT_TRACK: "1"` to the runtime's environment variables. The [diagrid package description](https://pypi.org/project/diagrid/0.5.3/) lists what is sent and the other opt-out variables.

## Clean Up

```bash
aws bedrock-agentcore-control delete-agent-runtime --region "$AWS_REGION" --agent-runtime-id "${RUNTIME_ARN##*/}"
aws iam delete-role-policy --role-name budget-planner-agentcore --policy-name budget-planner-agentcore
aws iam delete-role --role-name budget-planner-agentcore
aws secretsmanager delete-secret --secret-id "$AGENT_SECRET_ARN" --force-delete-without-recovery
rm -f trust-policy.json permissions.json response.json
diagrid project delete bedrock-quickstart
```
