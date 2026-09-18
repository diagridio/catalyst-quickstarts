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
	// maxTurns bounds the model/tool loop, so a model that asks for tools
	// without ever settling is stopped rather than followed.
	maxTurns = 4

	// envModel opts in to a real provider, and modelOpenAI is the one value
	// that does so.
	envModel    = "DIAGRID_QUICKSTART_MODEL"
	modelOpenAI = "openai"

	openAIModel = "gpt-4.1-mini"
)

var (
	errNoAnswer      = errors.New("the model asked for tools on every turn and never answered")
	errEmptyResponse = errors.New("the model returned no choices")
)

// agent is the whole agent: a model, and the tools it may call.
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

// buildModel returns a real provider on request, and the canned model otherwise.
func buildModel(offline bool) llms.Model {
	if os.Getenv(envModel) == modelOpenAI {
		model, err := openai.New(openai.WithModel(openAIModel))
		if err != nil {
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
// subject is the caller the middleware verified. It is an argument rather than
// a message precisely because a message is something the model can rewrite.
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

		// A model may say something AND ask for tools in the same turn.
		if choice.Content != "" {
			transcript = append(transcript, choice.Content)
		}
		messages = append(messages, assistantTurn(choice))

		results := llms.MessageContent{Role: llms.ChatMessageTypeTool}
		for _, call := range choice.ToolCalls {
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

// callTool runs one requested tool on behalf of the verified caller. The
// verified subject OVERRIDES whatever subject the model asked for: a model can
// request anybody's bookings, and only the verified caller's are ever served.
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
// sees the tool calls it asked for.
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

// withSubject returns a copy of args carrying the verified subject, so the
// substitution cannot be undone by anything still holding the original map.
func withSubject(args map[string]any, subject string) map[string]any {
	substituted := make(map[string]any, len(args)+1)
	for name, value := range args {
		substituted[name] = value
	}
	substituted[argSubject] = subject
	return substituted
}
