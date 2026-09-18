package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"strings"

	"github.com/diagridio/go-ai/identity"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/tmc/langchaingo/llms"
)

// This file holds the agent's tools, and the two trust stories they tell.
// my_bookings runs in-process and is handed the caller's subject as an
// argument. account_summary leaves the process, and carries the caller in a
// token Catalyst mints for that one call.

const (
	toolMyBookings     = "my_bookings"
	toolAccountSummary = "account_summary"

	// argSubject is the argument a tool takes the calling user as, and the name
	// the agent loop substitutes the verified subject over.
	argSubject = "subject"

	argAccountID = "account_id"

	// mcpServerName is the MCPServer resource registered by
	// resources/crm-mcp.yaml.
	mcpServerName = "crm-mcp"

	// mcpProxyPath is Catalyst's MCP proxy. Reaching a tool through this path
	// is what attaches the calling user; calling the CRM directly would not.
	mcpProxyPath = "/v1.0/diagrid/mcp/"

	defaultDaprEndpoint = "http://localhost:3500"

	envDaprHTTPEndpoint = "DAPR_HTTP_ENDPOINT"
	envDaprAPIToken     = "DAPR_API_TOKEN"

	// daprAPITokenHeader authenticates the app to its own sidecar. It is the
	// app's credential, entirely separate from the calling user's.
	daprAPITokenHeader = "dapr-api-token"
)

// tool is one tool the agent may call.
type tool struct {
	// declaration is the tool as the model sees it.
	declaration llms.Tool

	// invoke runs the tool. ctx is the inbound request's context, which is what
	// carries the caller on an outbound call.
	invoke func(ctx context.Context, args map[string]any) (string, error)
}

// takesSubject reports whether this tool takes the calling user as an argument,
// in which case the agent loop substitutes the verified subject over whatever
// the model asked for. It is derived from the declaration the model sees, so
// the two cannot disagree.
func (t tool) takesSubject() bool {
	return t.declares(argSubject)
}

// declares reports whether the tool's JSON Schema declares the named argument.
func (t tool) declares(name string) bool {
	if t.declaration.Function == nil {
		return false
	}
	parameters, ok := t.declaration.Function.Parameters.(map[string]any)
	if !ok {
		return false
	}
	properties, ok := parameters["properties"].(map[string]any)
	if !ok {
		return false
	}
	_, declared := properties[name]
	return declared
}

// localTools is the offline tool set, used when there is no Catalyst project
// behind the app and therefore no MCP server to reach.
func localTools() map[string]tool {
	return map[string]tool{
		toolMyBookings: {
			declaration: llms.Tool{
				Type: "function",
				Function: &llms.FunctionDefinition{
					Name:        toolMyBookings,
					Description: "List the bookings that belong to the calling user.",
					Parameters: objectSchema(
						map[string]any{
							argSubject: map[string]any{
								"type":        "string",
								"description": "The user whose bookings to list.",
							},
						},
						argSubject,
					),
				},
			},
			invoke: func(_ context.Context, args map[string]any) (string, error) {
				return myBookings(stringArg(args, argSubject)), nil
			},
		},
	}
}

// catalystTools is the tool set used against a Catalyst project: the one tool
// that leaves the process and carries the caller with it.
func catalystTools() map[string]tool {
	// Safe to share across requests: the caller is read off the request context
	// at send time, so concurrent requests each carry their own.
	client := newMCPHTTPClient()

	return map[string]tool{
		toolAccountSummary: {
			declaration: llms.Tool{
				Type: "function",
				Function: &llms.FunctionDefinition{
					Name:        toolAccountSummary,
					Description: "Summarise a CRM account. Runs as the user who invoked the agent.",
					Parameters: objectSchema(
						map[string]any{
							argAccountID: map[string]any{
								"type":        "string",
								"description": "The CRM account to summarise, such as ACME-1.",
							},
						},
						argAccountID,
					),
				},
			},
			invoke: func(ctx context.Context, args map[string]any) (string, error) {
				return accountSummary(ctx, client, stringArg(args, argAccountID))
			},
		},
	}
}

// myBookings lists the bookings that belong to the calling user. It runs
// in-process, so it trusts whatever subject the agent hands it; the agent loop
// is what makes that sound.
func myBookings(subject string) string {
	return fmt.Sprintf("Bookings for %s: "+
		"Grand Ballroom on March 15th, 9AM-1PM; "+
		"Rooftop Terrace on March 22nd, 6PM-11PM.", subject)
}

// --- The outbound half: calling a tool as the user -------------------------
// accountSummary takes no subject at all. The calling user travels in a token
// Catalyst mints for this one call, so the CRM establishes who is asking for
// itself rather than believing the agent.

// accountSummary summarises a CRM account, running as the user who invoked the
// agent.
//
// ctx must be the inbound request's context: the identity client reads the
// caller's token off it at send time, so a call built from context.Background()
// goes out with no user attached. The session is therefore built per request.
func accountSummary(ctx context.Context, client *http.Client, accountID string) (string, error) {
	transport := &mcp.StreamableClientTransport{
		Endpoint:   mcpURL(),
		HTTPClient: client,
		// Nothing here listens for server-initiated messages.
		DisableStandaloneSSE: true,
	}

	session, err := mcp.NewClient(&mcp.Implementation{
		Name:    "identity-agent",
		Version: "0.1.0",
	}, nil).Connect(ctx, transport, nil)
	if err != nil {
		return "", fmt.Errorf("connect to %s: %w", mcpServerName, err)
	}
	defer session.Close()

	result, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name:      toolAccountSummary,
		Arguments: map[string]any{argAccountID: accountID},
	})
	if err != nil {
		return "", fmt.Errorf("call %s: %w", toolAccountSummary, err)
	}
	return textContent(result)
}

// mcpURL is the tool's address on Catalyst's MCP proxy, resolved per call so a
// test can point the tool at a stand-in server.
func mcpURL() string {
	endpoint := os.Getenv(envDaprHTTPEndpoint)
	if endpoint == "" {
		endpoint = defaultDaprEndpoint
	}
	return strings.TrimRight(endpoint, "/") + mcpProxyPath + mcpServerName
}

// newMCPHTTPClient is the outbound client, and the whole of the outbound
// identity integration. Two credentials travel on the request: the identity
// transport attaches the CALLING USER, read off the request context, and the
// inner transport attaches the app's own sidecar API TOKEN. Identity wraps the
// API-token client rather than the other way round, because
// [identity.NewHTTPClient] keeps and wraps the transport it is handed.
func newMCPHTTPClient() *http.Client {
	return identity.NewHTTPClient(&http.Client{
		Transport: apiTokenTransport{token: os.Getenv(envDaprAPIToken)},
	})
}

// apiTokenTransport adds the sidecar API token to every outbound request.
type apiTokenTransport struct {
	token string

	// base is the next RoundTripper. nil means http.DefaultTransport.
	base http.RoundTripper
}

func (t apiTokenTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	next := t.base
	if next == nil {
		next = http.DefaultTransport
	}
	if t.token == "" {
		return next.RoundTrip(req)
	}
	// A RoundTripper must not modify the request it is given.
	clone := req.Clone(req.Context())
	clone.Header.Set(daprAPITokenHeader, t.token)
	return next.RoundTrip(clone)
}

// textContent is the tool's answer as text.
func textContent(result *mcp.CallToolResult) (string, error) {
	for _, content := range result.Content {
		if text, ok := content.(*mcp.TextContent); ok {
			return text.Text, nil
		}
	}
	if result.IsError {
		return "", fmt.Errorf("%s reported an error with no text content", toolAccountSummary)
	}
	return "", fmt.Errorf("%s returned no text content", toolAccountSummary)
}

// objectSchema is the JSON Schema a tool declares its arguments with.
func objectSchema(properties map[string]any, required ...string) map[string]any {
	return map[string]any{
		"type":       "object",
		"properties": properties,
		"required":   required,
	}
}

// stringArg reads a string argument, treating a missing or wrongly typed one as
// empty, so a tool answers for nobody rather than guessing.
func stringArg(args map[string]any, name string) string {
	value, _ := args[name].(string)
	return value
}
