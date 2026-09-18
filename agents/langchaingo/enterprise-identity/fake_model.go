package main

import (
	"context"
	"errors"
	"slices"

	"github.com/tmc/langchaingo/llms"
)

// This file holds a deterministic stand-in for a hosted chat model.
//
// This quickstart's point is identity, not model quality, so it ships a canned
// two-turn conversation: ask for the tool, then answer from the tool's result.
// That keeps the demo free, offline and identical on every run.
//
// Set OPENAI_API_KEY and DIAGRID_QUICKSTART_MODEL=openai to use a real
// provider.

// modelGuess is the subject the canned first turn asks the tool for. It is
// nobody. A model does not know who is calling and must not be trusted to
// decide -- the agent loop replaces this argument with the subject the
// middleware verified. A real provider behaves the same way, which is the point
// of substituting rather than validating.
const modelGuess = "someone@example.com"

// errCallNotSupported reports the deprecated single-prompt entry point, which
// this quickstart never uses.
var errCallNotSupported = errors.New("canned model supports GenerateContent only")

// cannedModel returns firstTurn until a tool has run, then finalTurn.
//
// The decision reads the conversation rather than counting calls. A call
// counter resets with the process and would ask for the tool a second time; the
// replayed message history is the only state that always tells the truth.
type cannedModel struct {
	firstTurn llms.ContentChoice
	finalTurn llms.ContentChoice
}

var _ llms.Model = cannedModel{}

// GenerateContent returns whichever canned turn the conversation has earned.
func (m cannedModel) GenerateContent(
	_ context.Context,
	messages []llms.MessageContent,
	_ ...llms.CallOption,
) (*llms.ContentResponse, error) {
	// The options are accepted and ignored: the tool call below is already
	// decided, so there is no schema for this model to read.
	turn := m.firstTurn
	if toolHasRun(messages) {
		turn = m.finalTurn
	}
	return &llms.ContentResponse{Choices: []*llms.ContentChoice{copyTurn(turn)}}, nil
}

// copyTurn returns a turn that shares nothing with the canned one, so a caller
// that edits the choice it is handed cannot change what the next turn returns.
//
// Copying the struct alone would not do it: the tool calls are a slice of
// structs holding a pointer each, so both the slice and every FunctionCall
// behind it are copied too.
func copyTurn(turn llms.ContentChoice) *llms.ContentChoice {
	copied := turn
	copied.ToolCalls = slices.Clone(turn.ToolCalls)
	for i, call := range copied.ToolCalls {
		if call.FunctionCall == nil {
			continue
		}
		function := *call.FunctionCall
		copied.ToolCalls[i].FunctionCall = &function
	}
	return &copied
}

// Call is the deprecated half of llms.Model. This quickstart's loop calls
// GenerateContent, so this reports rather than guesses.
func (m cannedModel) Call(_ context.Context, _ string, _ ...llms.CallOption) (string, error) {
	return "", errCallNotSupported
}

// toolHasRun reports whether any tool result is already in the conversation.
func toolHasRun(messages []llms.MessageContent) bool {
	for _, message := range messages {
		if message.Role == llms.ChatMessageTypeTool {
			return true
		}
	}
	return false
}

// buildCannedModel is the canned two-turn conversation this quickstart runs on.
//
// It lives here rather than in agent.go so that the tests can assert against
// the real thing instead of a copy of it. buildModel returns this.
//
// Note the subject the first turn asks for: modelGuess, who is nobody.
func buildCannedModel(offline bool) cannedModel {
	call := llms.ToolCall{
		ID:   "call_" + toolAccountSummary + "_1",
		Type: "function",
		FunctionCall: &llms.FunctionCall{
			Name:      toolAccountSummary,
			Arguments: `{"account_id": "ACME-1"}`,
		},
	}
	answer := "Here is what the CRM returned for ACME-1."

	if offline {
		call = llms.ToolCall{
			ID:   "call_" + toolMyBookings + "_1",
			Type: "function",
			FunctionCall: &llms.FunctionCall{
				Name:      toolMyBookings,
				Arguments: `{"subject": "` + modelGuess + `"}`,
			},
		}
		answer = "You have two bookings: the Grand Ballroom on March 15th " +
			"(9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM)."
	}

	return cannedModel{
		firstTurn: llms.ContentChoice{ToolCalls: []llms.ToolCall{call}},
		finalTurn: llms.ContentChoice{Content: answer},
	}
}
