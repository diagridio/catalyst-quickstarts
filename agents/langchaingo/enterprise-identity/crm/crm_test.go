// Tests for the CRM's half of the on-behalf-of story: that it establishes who
// the call is for from the token Catalyst minted, and reports both parties.
// Nothing here needs an issuer, because the CRM never verifies the token.
package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/diagridio/go-ai/identity"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const (
	testUser    = "auth0-user@example.com"
	testAgent   = "spiffe://catalyst/ns/prj-demo/identity-agent"
	testAccount = "ACME-1"
)

// userToken builds a compact JWT whose payload carries claims. It is not signed
// with anything, because the CRM decodes and never verifies.
func userToken(t *testing.T, claims map[string]any) string {
	t.Helper()

	segment := func(value any) string {
		encoded, err := json.Marshal(value)
		if err != nil {
			t.Fatalf("marshal token segment: %v", err)
		}
		return base64.RawURLEncoding.EncodeToString(encoded)
	}
	return strings.Join([]string{
		segment(map[string]any{"alg": "RS256", "typ": "JWT"}),
		segment(claims),
		"not-a-real-signature",
	}, ".")
}

// headerClient is an http.Client that sets the user-token header on every
// request, standing in for what identity.NewHTTPClient does on the agent's
// side. What is under test is the CRM reading the header.
func headerClient(header string) *http.Client {
	return &http.Client{Transport: headerTransport{header: header}}
}

type headerTransport struct {
	header string
}

func (t headerTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	clone := req.Clone(req.Context())
	if t.header != "" {
		clone.Header.Set(identity.UserTokenHeader, t.header)
	}
	return http.DefaultTransport.RoundTrip(clone)
}

// onBehalfOfClaims is the shape Catalyst mints for an agent calling as a user:
// `sub` is the user, and `act.sub` is the agent acting for them.
func onBehalfOfClaims() map[string]any {
	return map[string]any{
		"sub": testUser,
		"act": map[string]any{"sub": testAgent},
	}
}

// callTool drives the CRM the way the agent does: streamable HTTP through the
// real handler, with whatever user-token header the caller passes.
func callTool(t *testing.T, header string) string {
	t.Helper()

	server := httptest.NewServer(newMux())
	defer server.Close()

	session, err := mcp.NewClient(&mcp.Implementation{Name: "test-agent", Version: "0.1.0"}, nil).
		Connect(context.Background(), &mcp.StreamableClientTransport{
			Endpoint:             server.URL + mcpPath,
			HTTPClient:           headerClient(header),
			DisableStandaloneSSE: true,
		}, nil)
	if err != nil {
		t.Fatalf("connect to the crm: %v", err)
	}
	defer session.Close()

	result, err := session.CallTool(context.Background(), &mcp.CallToolParams{
		Name:      toolAccountSummary,
		Arguments: map[string]any{"account_id": testAccount},
	})
	if err != nil {
		t.Fatalf("call %s: %v", toolAccountSummary, err)
	}

	for _, content := range result.Content {
		if text, ok := content.(*mcp.TextContent); ok {
			return text.Text
		}
	}
	t.Fatalf("the crm returned no text content")
	return ""
}

func TestTheCRMReportsBothIdentitiesFromTheToken(t *testing.T) {
	// The CRM names the user AND the agent, having been told neither.
	answer := callTool(t, identity.BearerPrefix+userToken(t, onBehalfOfClaims()))

	for _, want := range []string{
		"Account " + testAccount + ": 3 open opportunities, $120k pipeline.",
		"user=" + testUser,
		"agent=" + testAgent,
	} {
		if !strings.Contains(answer, want) {
			t.Errorf("answer %q does not contain %q", answer, want)
		}
	}
}

func TestTheCRMSaysSoWhenTheCallCarriesNoUser(t *testing.T) {
	// requireUser: false on the access policy, or a call the agent made outside
	// a verified request, both look like this.
	cases := []struct {
		name   string
		header string
	}{
		{name: "no header", header: ""},
		{name: "not a jwt", header: identity.BearerPrefix + "not-a-jwt"},
		{name: "payload is not json", header: identity.BearerPrefix +
			"header." + base64.RawURLEncoding.EncodeToString([]byte("nope")) + ".signature"},
	}

	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			answer := callTool(t, test.header)

			if !strings.Contains(answer, "user="+noUser) {
				t.Errorf("answer %q does not report a missing user", answer)
			}
			if !strings.Contains(answer, "agent="+noAgent) {
				t.Errorf("answer %q does not report a missing agent", answer)
			}
		})
	}
}

func TestTheSchemePrefixIsMatchedCaseInsensitively(t *testing.T) {
	// A case-sensitive trim would take "bearer " as part of the token and report
	// no user at all.
	for _, prefix := range []string{"Bearer ", "bearer ", "BEARER "} {
		t.Run(strings.TrimSpace(prefix), func(t *testing.T) {
			if answer := callTool(t, prefix+userToken(t, onBehalfOfClaims())); !strings.Contains(
				answer, "user="+testUser) {
				t.Errorf("answer %q does not name the calling user", answer)
			}
		})
	}
}

func TestAnActorClaimThatIsNotAnObjectReportsNoAgent(t *testing.T) {
	// Fail closed: reporting the raw value as an agent identity would put
	// unvalidated token content in the answer.
	claims := map[string]any{"sub": testUser, "act": "not-an-object"}

	answer := callTool(t, identity.BearerPrefix+userToken(t, claims))

	if !strings.Contains(answer, "user="+testUser) {
		t.Errorf("answer %q does not name the calling user", answer)
	}
	if !strings.Contains(answer, "agent="+noAgent) {
		t.Errorf("answer %q does not report a missing agent", answer)
	}
}
