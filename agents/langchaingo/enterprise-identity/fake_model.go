package main

import (
	"context"
	"errors"
	"slices"

	"github.com/tmc/langchaingo/llms"
)

// This file holds a deterministic stand-in for a hosted chat model: a canned
// two-turn conversation, so the demo is free, offline and identical on every
// run. Set OPENAI_API_KEY and DIAGRID_QUICKSTART_MODEL=openai for a real
// provider.

// modelGuess is the subject the canned first turn asks the tool for, and it is
// nobody. A model does not know who is calling and must not be trusted to
// decide; the agent loop replaces this argument with the verified subject.
const modelGuess = "someone@example.com"

var errCallNotSupported = errors.New("canned model supports GenerateContent only")

// cannedModel returns firstTurn until a tool has run, then finalTurn, reading
// the conversation rather than counting calls.
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
	turn := m.firstTurn
	if toolHasRun(messages) {
		turn = m.finalTurn
	}
	return &llms.ContentResponse{Choices: []*llms.ContentChoice{copyTurn(turn)}}, nil
}

// copyTurn returns a turn that shares nothing with the canned one, so a caller
// that edits the choice it is handed cannot change what the next turn returns.
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

// Call is the deprecated half of llms.Model, which this quickstart never uses.
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
