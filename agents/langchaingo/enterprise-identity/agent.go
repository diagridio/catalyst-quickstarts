package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"

	"github.com/tmc/langchaingo/llms"
	"github.com/tmc/langchaingo/llms/openai"
)

const (
	// maxTurns bounds the model/tool loop. The canned model answers on its
	// second turn, so anything past a handful means a real provider is asking
	// for tools without ever settling -- a runaway to stop rather than a
	// conversation to continue.
	maxTurns = 4

	// envModel opts in to a real provider, and modelOpenAI is the one value
	// that does so.
	envModel    = "DIAGRID_QUICKSTART_MODEL"
	modelOpenAI = "openai"

	// openAIModel is the model used when a reader opts in. Any provider
	// langchaingo supports works the same way; the identity behaviour is
	// identical either way.
	openAIModel = "gpt-4.1-mini"
)

var (
	// errNoAnswer reports a loop that ran out of turns without the model ever
	// returning text.
	errNoAnswer = errors.New("the model asked for tools on every turn and never answered")

	// errEmptyResponse reports a model turn that returned no choices at all,
	// which is a provider fault rather than a conversation that went wrong.
	errEmptyResponse = errors.New("the model returned no choices")
)

// agent is the whole agent: a model, and the tools it may call.
//
// This is a plain loop, not a workflow. There is no Diagrid agent runner, no
// Dapr Workflow and no durable state, so you can see exactly where identity
// enters and how little of the agent knows about it -- which is nothing: the
// only Diagrid-aware line in this file is the absence of one.
type agent struct {
	model llms.Model

	// tools is what run may invoke, keyed by the name the model asks for.
	tools map[string]tool

	// declarations is the same set as the model sees it.
	declarations []llms.Tool
}

// newAgent assembles the agent for the identity plane the app trusts.
func newAgent(offline bool) *agent {
	tools := catalystTools()
	if offline {
		tools = localTools()
	}

	declarations := make([]llms.Tool, 0, len(tools))
	for _, t := range tools {
		declarations = append(declarations, t.declaration)
	}

	return &agent{
		model:        buildModel(offline),
		tools:        tools,
		declarations: declarations,
	}
}

// buildModel returns a real provider on request, and the canned model
// otherwise.
func buildModel(offline bool) llms.Model {
	if os.Getenv(envModel) == modelOpenAI {
		model, err := openai.New(openai.WithModel(openAIModel))
		if err != nil {
			// A key that is missing or rejected is a configuration mistake, and
			// the app has nothing to serve without a model.
			log.Fatalf("openai model (%s): %v", openAIModel, err)
		}
		log.Printf("Using OpenAI (%s).", openAIModel)
		return model
	}

	log.Printf("Using the canned offline model: no API key needed and the answer is " +
		"always the same. Set " + envModel + "=" + modelOpenAI + " for a real provider.")
	return buildCannedModel(offline)
}

// run holds the conversation on behalf of the verified caller: call the model,
// run whatever tools it asks for, feed the results back, and stop when it
// answers in text.
//
// subject is the caller the middleware verified, passed in by the HTTP handler.
// It is an argument rather than a message precisely because a message is
// something the model can rewrite.
//
// The returned slice is the conversation a reader sees in the response: the
// task, each tool's answer, and the model's summary. The assistant turn that
// carries only tool calls has no content, so it is not in it.
func (a *agent) run(ctx context.Context, task, subject string) ([]string, error) {
	messages := []llms.MessageContent{llms.TextParts(llms.ChatMessageTypeHuman, task)}
	transcript := []string{task}

	for range maxTurns {
		response, err := a.model.GenerateContent(ctx, messages, llms.WithTools(a.declarations))
		if err != nil {
			return nil, fmt.Errorf("model turn: %w", err)
		}
		if len(response.Choices) == 0 {
			return nil, errEmptyResponse
		}
		choice := response.Choices[0]

		if len(choice.ToolCalls) == 0 {
			return append(transcript, choice.Content), nil
		}

		// A model may say something AND ask for tools in the same turn. The
		// turn that carries only tool calls has no content and contributes
		// nothing here, which is why the canned conversation reads as three
		// messages rather than four.
		if choice.Content != "" {
			transcript = append(transcript, choice.Content)
		}
		messages = append(messages, assistantTurn(choice))

		results := llms.MessageContent{Role: llms.ChatMessageTypeTool}
		for _, call := range choice.ToolCalls {
			// callTool rejects a call carrying no FunctionCall, so reading its
			// Name below is safe only after this has succeeded.
			answer, err := a.callTool(ctx, call, subject)
			if err != nil {
				return nil, err
			}
			transcript = append(transcript, answer)
			results.Parts = append(results.Parts, llms.ToolCallResponse{
				ToolCallID: call.ID,
				Name:       call.FunctionCall.Name,
				Content:    answer,
			})
		}
		messages = append(messages, results)
	}

	return nil, errNoAnswer
}

// callTool runs one requested tool on behalf of the verified caller.
//
// This is where the whole thesis of the quickstart lives. The verified subject
// OVERRIDES whatever subject the model asked for: a model can request anybody's
// bookings, and only the verified caller's are ever served. Substituting beats
// validating here -- there is no version of this where the model's opinion of
// who is calling matters.
func (a *agent) callTool(ctx context.Context, call llms.ToolCall, subject string) (string, error) {
	if call.FunctionCall == nil {
		return "", errors.New("model requested a tool call carrying no function")
	}
	name := call.FunctionCall.Name
	t, ok := a.tools[name]
	if !ok {
		return "", fmt.Errorf("model requested unknown tool %q", name)
	}

	args, err := decodeArguments(call.FunctionCall.Arguments)
	if err != nil {
		return "", fmt.Errorf("tool %q arguments: %w", name, err)
	}
	if t.takesSubject() {
		args = withSubject(args, subject)
	}

	log.Printf("[IDENTITY] tool call for subject=%s", subject)
	return t.invoke(ctx, args)
}

// assistantTurn is the model's own turn, replayed back to it so the next turn
// sees the tool calls it asked for. A tool result with no matching call is a
// protocol error to a real provider.
func assistantTurn(choice *llms.ContentChoice) llms.MessageContent {
	turn := llms.MessageContent{Role: llms.ChatMessageTypeAI}
	if choice.Content != "" {
		turn.Parts = append(turn.Parts, llms.TextPart(choice.Content))
	}
	for _, call := range choice.ToolCalls {
		turn.Parts = append(turn.Parts, call)
	}
	return turn
}

// decodeArguments parses the JSON argument object a model sends. An empty
// string is a call with no arguments, not a malformed one.
func decodeArguments(raw string) (map[string]any, error) {
	if raw == "" {
		return map[string]any{}, nil
	}
	var args map[string]any
	if err := json.Unmarshal([]byte(raw), &args); err != nil {
		return nil, err
	}
	if args == nil {
		args = map[string]any{}
	}
	return args, nil
}

// withSubject returns a copy of args carrying the verified subject, leaving the
// model's own arguments untouched. A copy rather than an assignment so the
// substitution cannot be undone by anything still holding the original map.
func withSubject(args map[string]any, subject string) map[string]any {
	substituted := make(map[string]any, len(args)+1)
	for name, value := range args {
		substituted[name] = value
	}
	substituted[argSubject] = subject
	return substituted
}
