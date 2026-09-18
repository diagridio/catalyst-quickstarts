// Command crm-server is a stand-in CRM, exposed over MCP. Its one tool reports
// the identity the call arrived with: the agent sends no password and no API
// key, and the CRM still knows whose question it is answering.
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
	// defaultAppPort is the port dev-enterprise-identity.yaml declares.
	defaultAppPort = "8007"

	envAppPort = "APP_PORT"

	// mcpPath is the endpoint resources/crm-mcp.yaml registers with Catalyst.
	mcpPath = "/mcp"

	// toolAccountSummary is the tool the agent calls, named by the same string
	// on its side. Two processes, so the constant cannot be shared.
	toolAccountSummary = "account_summary"

	// claimSubject is the calling user, and claimActor the agent acting for
	// them: RFC 8693 names the on-behalf-of claim `act`, whose own `sub` is the
	// delegate.
	claimSubject = "sub"
	claimActor   = "act"

	noUser  = "<no user identity>"
	noAgent = "<no agent>"

	jwtSegments = 3
)

// accountArgs is the tool's input. The struct tags give the MCP SDK the
// argument name and the schema description.
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
	// Requests arrive through Catalyst, whose Host is not loopback.
	mux.Handle(mcpPath, mcp.NewStreamableHTTPHandler(
		func(*http.Request) *mcp.Server { return server },
		&mcp.StreamableHTTPOptions{DisableLocalhostProtection: true}))
	return mux
}

// accountSummary summarises a CRM account, and reports who the CRM is
// answering. Both identities come off the token Catalyst minted for this one
// call; the agent was never asked who the user is.
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
// decision on these claims would have to verify the token itself.
func callingUser(req *mcp.CallToolRequest) map[string]any {
	if req == nil || req.Extra.Header == nil {
		return nil
	}
	raw := strings.TrimSpace(req.Extra.Header.Get(identity.UserTokenHeader))
	// Case-insensitively: only the spelling of the scheme prefix varies.
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
