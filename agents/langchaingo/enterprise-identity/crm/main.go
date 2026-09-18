// Command crm-server is a stand-in CRM, exposed over MCP.
//
// Its one tool reports the identity the call arrived with. The agent sends no
// password and no API key, and the CRM still knows whose question it is
// answering -- and which agent asked on their behalf.
package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/diagridio/go-ai/identity"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const (
	// defaultAppPort is the port dev-enterprise-identity.yaml declares for this
	// app, used when APP_PORT is unset.
	defaultAppPort = "8007"

	envAppPort = "APP_PORT"

	// mcpPath is the endpoint resources/crm-mcp.yaml registers with Catalyst.
	mcpPath = "/mcp"

	// toolAccountSummary is the tool the agent calls. The agent names the same
	// string on its side; they are two processes, so the constant cannot be
	// shared, but a mismatch is a tool-not-found error rather than a silent one.
	toolAccountSummary = "account_summary"

	// claimSubject is the calling user, and claimActor the agent acting for
	// them. The actor claim is the on-behalf-of half of the token: RFC 8693
	// names it `act`, and its own `sub` is the delegate.
	claimSubject = "sub"
	claimActor   = "act"

	// The placeholders reported when the token names nobody, so the difference
	// between "no user" and "no agent" is legible in the answer itself.
	noUser  = "<no user identity>"
	noAgent = "<no agent>"

	// jwtSegments is how many dot-separated parts a compact JWT has.
	jwtSegments = 3
)

// accountArgs is the tool's input. Struct tags give the MCP SDK the argument
// name and the schema description.
type accountArgs struct {
	AccountID string `json:"account_id" jsonschema:"the CRM account to summarise"`
}

func main() {
	addr := "0.0.0.0:" + appPort()
	log.Printf("listening on http://%s%s", addr, mcpPath)
	if err := http.ListenAndServe(addr, newMux()); err != nil {
		log.Fatalf("serve: %v", err)
	}
}

// newMCPServer is the CRM and its one tool.
func newMCPServer() *mcp.Server {
	server := mcp.NewServer(&mcp.Implementation{
		Name:    "crm",
		Version: "0.1.0",
	}, nil)

	// The generic AddTool derives the tool's input schema from accountArgs.
	mcp.AddTool(server, &mcp.Tool{
		Name:        toolAccountSummary,
		Description: "Summarise a CRM account, and report who the CRM is answering.",
	}, accountSummary)

	return server
}

// newMux serves the CRM over streamable HTTP at the path
// resources/crm-mcp.yaml registers.
func newMux() *http.ServeMux {
	server := newMCPServer()
	mux := http.NewServeMux()
	mux.Handle(mcpPath, mcp.NewStreamableHTTPHandler(
		func(*http.Request) *mcp.Server { return server }, nil))
	return mux
}

// accountSummary summarises a CRM account, and reports who the CRM is
// answering.
//
// Both identities come off the token Catalyst minted for this one call. The
// agent was never asked who the user is, and could not have been believed if it
// had been.
func accountSummary(
	_ context.Context,
	req *mcp.CallToolRequest,
	args accountArgs,
) (*mcp.CallToolResult, any, error) {
	claims := callingUser(req)
	user := claimString(claims, claimSubject, noUser)

	agent := noAgent
	if actor, ok := claims[claimActor].(map[string]any); ok {
		agent = claimString(actor, claimSubject, noAgent)
	}

	log.Printf("account_summary(%s) for user=%s via agent=%s", args.AccountID, user, agent)
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf(
			"Account %s: 3 open opportunities, $120k pipeline. "+
				"Served to user=%s via agent=%s.", args.AccountID, user, agent)}},
	}, nil, nil
}

// callingUser reads the calling user from the token Catalyst minted for this
// request.
//
// Catalyst verifies the signature before the request arrives, so this only
// DECODES the claims in order to show them. A service making an authorization
// decision on these claims would have to verify the token itself; this one only
// reports what it was told, which is the whole of its job.
//
// An unreadable or absent token is an empty claim set rather than an error: the
// tool's answer then says so, which is more use to a reader than a protocol
// failure with no explanation.
func callingUser(req *mcp.CallToolRequest) map[string]any {
	if req == nil || req.Extra.Header == nil {
		return nil
	}
	raw := strings.TrimSpace(req.Extra.Header.Get(identity.UserTokenHeader))
	// Case-insensitively, because the scheme prefix is written by clients in
	// several languages and only its spelling varies.
	token := raw
	if len(raw) >= len(identity.BearerPrefix) &&
		strings.EqualFold(raw[:len(identity.BearerPrefix)], identity.BearerPrefix) {
		token = raw[len(identity.BearerPrefix):]
	}
	token = strings.TrimSpace(token)
	if token == "" {
		return nil
	}

	segments := strings.Split(token, ".")
	if len(segments) != jwtSegments {
		log.Printf("user token is not a compact JWT; reporting no identity")
		return nil
	}
	// RawURLEncoding, because a JWT segment is base64url with the padding
	// stripped.
	payload, err := base64.RawURLEncoding.DecodeString(segments[1])
	if err != nil {
		log.Printf("decode user token payload: %v", err)
		return nil
	}

	var claims map[string]any
	if err := json.Unmarshal(payload, &claims); err != nil {
		log.Printf("parse user token payload: %v", err)
		return nil
	}
	return claims
}

// claimString reads a string claim, falling back to absent when it is missing
// or not a string.
func claimString(claims map[string]any, name, absent string) string {
	value, ok := claims[name].(string)
	if !ok || value == "" {
		return absent
	}
	return value
}

func appPort() string {
	if port := os.Getenv(envAppPort); port != "" {
		return port
	}
	return defaultAppPort
}
