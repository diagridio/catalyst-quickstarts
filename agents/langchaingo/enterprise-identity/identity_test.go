//go:build offline

// Tests for the identity behaviour this quickstart demonstrates.
//
// Run from this directory with:
//
//	go test -tags offline ./...
//
// The `offline` build tag is required, not incidental: it is what compiles
// local_identity.go in, and that is the only thing here that can mint a
// credential the app accepts. Without it the package has no issuer, which is
// exactly the property the shipped image relies on.
//
// No Catalyst, no Dapr, no network off loopback and no API key. buildLocalIssuer
// stands in for the Catalyst identity plane: it signs with a throwaway key it
// generates in-process and serves the public half as JWKS on a loopback port,
// so a credential that genuinely verifies is available offline. That is what
// makes the 200 and the 403 assertable here at all -- the Robot suite next door
// can present no credential and therefore asserts only the two 401s.
//
// The app is assembled from its own constructors rather than rebuilt: newHandler
// and newAgent are main.go's, so drift in the routes, the middleware install,
// the agent loop or the response shape fails these tests rather than sliding
// past. Only the OAuthConfig is this test's, because pointing the middleware at
// the throwaway issuer is the whole point.
//
// WHAT IS DELIBERATELY NOT TESTED AGAINST CATALYST: the outbound leg as Catalyst
// runs it. Carrying the caller onward through Catalyst's MCP proxy needs a
// project, so the walkthrough in the README covers that. What IS tested here is
// the half that is this app's responsibility and the likeliest thing to get
// wrong in Go: that the outbound request is built from the inbound request's
// context, so the caller's token is attached at all. See
// TestOutboundCallCarriesTheCallerOnlyFromTheInboundContext.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/diagridio/go-ai/identity"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const (
	// verifiedSubject is the subject of the credential buildLocalIssuer mints
	// under `200`. The other two it mints -- bob@example.com without the scope
	// and carol@example.com five minutes stale -- are refused before any
	// subject reaches the app, so only this one is named here.
	verifiedSubject = "alice@example.com"

	task = "What bookings do I have?"

	// toolAnswerForVerifiedCaller and modelAnswer are the exact strings the
	// README's offline section prints. Asserting them keeps the documented
	// output honest.
	toolAnswerForVerifiedCaller = "Bookings for alice@example.com: " +
		"Grand Ballroom on March 15th, 9AM-1PM; Rooftop Terrace on March 22nd, 6PM-11PM."
	modelAnswer = "You have two bookings: the Grand Ballroom on March 15th " +
		"(9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM)."
)

// app is the app under test: main.go's handlers behind main.go's middleware,
// plus the credentials the issuer behind it accepts.
type app struct {
	handler http.Handler
	issuer  localIssuer
}

// newTestApp assembles the app once per test that needs it.
//
// Generating an RSA key is not free, so tests that only need the fail-closed
// paths share one via the package-level helper below rather than each building
// their own.
func newTestApp(t *testing.T) app {
	t.Helper()

	issuer, err := buildLocalIssuer(localRequiredScopes())
	if err != nil {
		t.Fatalf("build local issuer: %v", err)
	}
	// Offline: the agent gets the in-process tool, so no request leaves the
	// machine for a tool call.
	return app{handler: newHandler(issuer.config, newAgent(true)), issuer: issuer}
}

// sharedApp is one app for the whole package, built on first use.
var sharedApp *app

func testApp(t *testing.T) app {
	t.Helper()
	if sharedApp == nil {
		built := newTestApp(t)
		sharedApp = &built
	}
	return *sharedApp
}

// do sends a request through the app and returns the recorded response.
func (a app) do(t *testing.T, method, path string, body any, headers map[string]string) *httptest.ResponseRecorder {
	t.Helper()

	var reader io.Reader
	switch payload := body.(type) {
	case nil:
	case string:
		// A raw string is sent verbatim, which is how the not-JSON case is
		// expressed.
		reader = strings.NewReader(payload)
	default:
		encoded, err := json.Marshal(payload)
		if err != nil {
			t.Fatalf("marshal request body: %v", err)
		}
		reader = strings.NewReader(string(encoded))
	}

	request := httptest.NewRequest(method, path, reader)
	if reader != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	for name, value := range headers {
		request.Header.Set(name, value)
	}

	recorder := httptest.NewRecorder()
	a.handler.ServeHTTP(recorder, request)
	return recorder
}

// auth is the header Catalyst sets on an inbound request, as the middleware
// reads it.
func auth(token string) map[string]string {
	return map[string]string{identity.UserTokenHeader: identity.BearerPrefix + token}
}

// decode parses a JSON response body, failing the test if it is not JSON.
func decode[T any](t *testing.T, recorder *httptest.ResponseRecorder) T {
	t.Helper()
	var body T
	if err := json.Unmarshal(recorder.Body.Bytes(), &body); err != nil {
		t.Fatalf("parse response body %q: %v", recorder.Body.String(), err)
	}
	return body
}

// assertRefused checks a refusal: the status, the exact error code, and nothing
// else in the envelope.
func assertRefused(t *testing.T, recorder *httptest.ResponseRecorder, status int, code string) {
	t.Helper()
	if recorder.Code != status {
		t.Errorf("status = %d, want %d (body %q)", recorder.Code, status, recorder.Body.String())
	}
	body := decode[map[string]string](t, recorder)
	if want := (map[string]string{"error": code}); len(body) != 1 || body["error"] != code {
		t.Errorf("body = %v, want %v", body, want)
	}
}

// --- Fail closed, before any application code runs -------------------------

func TestNoCredentialIsRefusedOnEveryRoute(t *testing.T) {
	// RequireAuth resolves to true on the zero OAuthConfig and the middleware
	// wraps every route, so this is the app-wide rule the README claims, checked
	// on both documented routes rather than on one and assumed for the other.
	// The exact body is the one the Robot suite asserts against a live Catalyst
	// project.
	cases := []struct {
		name   string
		method string
		path   string
		body   any
	}{
		{name: "whoami", method: http.MethodGet, path: "/whoami"},
		{name: "agent run", method: http.MethodPost, path: "/agent/run", body: map[string]string{"task": task}},
	}

	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			recorder := testApp(t).do(t, test.method, test.path, test.body, nil)

			assertRefused(t, recorder, http.StatusUnauthorized, identity.ErrorCodeMissingToken)
			// An authorization verdict is not a cacheable response. This header
			// is the middleware's, not this app's, and the README documents it.
			if got := recorder.Header().Get("Cache-Control"); got != "no-store" {
				t.Errorf("Cache-Control = %q, want %q", got, "no-store")
			}
		})
	}
}

func TestAnEmptyHeaderIsTreatedAsNoCredential(t *testing.T) {
	// The README claims "no header, or an empty one" is 401, so both halves are
	// checked. The SDK trims the header, so a blank value leaves an empty token
	// and takes the same branch as an absent header.
	for _, value := range []string{"", "   "} {
		t.Run(fmt.Sprintf("%q", value), func(t *testing.T) {
			recorder := testApp(t).do(t, http.MethodGet, "/whoami", nil,
				map[string]string{identity.UserTokenHeader: value})

			assertRefused(t, recorder, http.StatusUnauthorized, identity.ErrorCodeMissingToken)
		})
	}
}

func TestACredentialWithoutTheRequiredScopeIs403(t *testing.T) {
	// 403, not 401, and the distinction is the point: authentication succeeded
	// and authorization failed. The credential is signed by the same issuer and
	// has not expired -- it simply carries reports.read.
	a := testApp(t)
	recorder := a.do(t, http.MethodGet, "/whoami", nil, auth(a.issuer.wrongScope))

	assertRefused(t, recorder, http.StatusForbidden, identity.ErrorCodeMissingScope)
}

func TestAnExpiredCredentialIs401(t *testing.T) {
	// Five minutes stale, because the verifier allows 120s of clock skew. If
	// expiredTokenLifetime ever creeps inside that window this returns 200 and
	// fails here rather than in a reader's terminal.
	a := testApp(t)
	recorder := a.do(t, http.MethodGet, "/whoami", nil, auth(a.issuer.expired))

	assertRefused(t, recorder, http.StatusUnauthorized, identity.ErrorCodeExpired)
}

func TestAMalformedTokenIs401(t *testing.T) {
	cases := []struct {
		name   string
		header string
	}{
		{name: "not a jwt", header: identity.BearerPrefix + "not-a-jwt"},
		// A bare "Bearer" with nothing after it, which looks like an empty
		// credential but is not one. BearerPrefix is "Bearer " -- the trailing
		// space is part of it -- and HTTP strips trailing header whitespace, so
		// the prefix never matches and the literal string "Bearer" is taken as
		// the token. It therefore lands here, among the malformed tokens, rather
		// than on the oauth.missing_token path an empty header gets. Same status
		// either way, but a different code, and that is worth pinning.
		{name: "bare bearer", header: "Bearer"},
	}

	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			// Asserting the code and not just the status: 401 alone would still
			// pass if a future version routed this through missing_token or
			// invalid_signature, and those mean different things to a reader
			// debugging a real credential.
			recorder := testApp(t).do(t, http.MethodGet, "/whoami", nil,
				map[string]string{identity.UserTokenHeader: test.header})

			assertRefused(t, recorder, http.StatusUnauthorized, identity.ErrorCodeDecodeError)
		})
	}
}

// --- The verified caller reaches the app ------------------------------------

func TestAVerifiedCallerGetsTheDocumentedIdentity(t *testing.T) {
	a := testApp(t)
	recorder := a.do(t, http.MethodGet, "/whoami", nil, auth(a.issuer.verified))

	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", recorder.Code, recorder.Body.String())
	}

	// The exact object the README's offline section prints.
	got := decode[identityResponse](t, recorder)
	want := identityResponse{
		Subject:  verifiedSubject,
		Tenant:   localTenant,
		IssuerID: localIssuerName,
		Scopes:   localRequiredScopes(),
	}
	if got.Subject != want.Subject || got.Tenant != want.Tenant || got.IssuerID != want.IssuerID {
		t.Errorf("identity = %+v, want %+v", got, want)
	}
	if len(got.Scopes) != 1 || got.Scopes[0] != localRequiredScope {
		t.Errorf("scopes = %v, want %v", got.Scopes, want.Scopes)
	}

	// Claim NAMES only, and EXACTLY these four. VerifiedUser.Claims is a real
	// person's decoded credential in a deployment, so the check is on the whole
	// key set rather than on the absence of one field name: a future handler
	// that exposed `claims`, or any other claim value under any name, fails
	// here.
	raw := decode[map[string]any](t, recorder)
	documented := map[string]bool{"subject": true, "tenant": true, "issuer_id": true, "scopes": true}
	for name := range raw {
		if !documented[name] {
			t.Errorf("response carries undocumented field %q = %v; /whoami exposes "+
				"claim names only", name, raw[name])
		}
	}
	for name := range documented {
		if _, ok := raw[name]; !ok {
			t.Errorf("response is missing the documented field %q", name)
		}
	}
}

func TestTheToolAnswersForTheVerifiedCallerNotTheModelGuess(t *testing.T) {
	// The thesis of the whole quickstart, asserted end to end. The canned model
	// asks my_bookings for someone@example.com; the agent loop substitutes the
	// subject the middleware verified, so the answer names alice@example.com and
	// the model's guess appears nowhere in the response.
	a := testApp(t)
	recorder := a.do(t, http.MethodPost, "/agent/run",
		map[string]string{"task": task}, auth(a.issuer.verified))

	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200 (body %q)", recorder.Code, recorder.Body.String())
	}

	body := decode[agentRunResponse](t, recorder)
	if body.User.Subject != verifiedSubject {
		t.Errorf("user.subject = %q, want %q", body.User.Subject, verifiedSubject)
	}
	// The exact three messages the README's offline section prints: the task,
	// the tool's answer, and the model's summary of it.
	want := []string{task, toolAnswerForVerifiedCaller, modelAnswer}
	if len(body.Messages) != len(want) {
		t.Fatalf("messages = %q, want %q", body.Messages, want)
	}
	for i, message := range want {
		if body.Messages[i] != message {
			t.Errorf("messages[%d] = %q, want %q", i, body.Messages[i], message)
		}
	}
	if strings.Contains(recorder.Body.String(), modelGuess) {
		t.Errorf("the model's guessed subject %q reached the response, so the agent "+
			"loop stopped substituting the verified subject", modelGuess)
	}
}

func TestSubstitutionHappensInTheAgentLoopNotInTheHandler(t *testing.T) {
	// Run the real agent directly, with no HTTP and no middleware. This proves
	// the substitution lives in the loop's tool call rather than in the route
	// handler, which is exactly why a message the model could rewrite is not
	// involved.
	messages, err := newAgent(true).run(context.Background(), task, "dave@example.com")
	if err != nil {
		t.Fatalf("agent run: %v", err)
	}

	joined := strings.Join(messages, "\n")
	if !strings.Contains(joined, "Bookings for dave@example.com") {
		t.Errorf("the tool did not answer for the subject the loop was given: %q", joined)
	}
	if strings.Contains(joined, modelGuess) {
		t.Errorf("the model's guessed subject %q reached the tool: %q", modelGuess, joined)
	}
}

func TestAnUnsetSubjectDoesNotSilentlyBecomeTheModelGuess(t *testing.T) {
	// A missing subject must not fall back to the model's argument. The loop
	// substitutes unconditionally, so an agent run with no subject answers for
	// nobody. That is the safe direction; falling through to the model's
	// someone@example.com would be the unsafe one.
	messages, err := newAgent(true).run(context.Background(), task, "")
	if err != nil {
		t.Fatalf("agent run: %v", err)
	}

	if joined := strings.Join(messages, "\n"); strings.Contains(joined, modelGuess) {
		t.Errorf("the model's guessed subject %q reached the tool: %q", modelGuess, joined)
	}
}

// --- Request validation -----------------------------------------------------

func TestATaskThatIsNotANonEmptyStringIs400(t *testing.T) {
	cases := []struct {
		name string
		body any
	}{
		{name: "no task", body: map[string]any{}},
		{name: "empty task", body: map[string]any{"task": ""}},
		{name: "blank task", body: map[string]any{"task": "   "}},
		{name: "task is a number", body: map[string]any{"task": 7}},
		{name: "body is an array", body: []any{}},
	}

	a := testApp(t)
	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			// Validated after authentication, so a bad body from a verified
			// caller is a 400 while the same body from an anonymous one is
			// still a 401.
			recorder := a.do(t, http.MethodPost, "/agent/run", test.body, auth(a.issuer.verified))

			if recorder.Code != http.StatusBadRequest {
				t.Fatalf("status = %d, want 400 (body %q)", recorder.Code, recorder.Body.String())
			}
			if got := decode[errorResponse](t, recorder); got.Error != errorBadRequest {
				t.Errorf("error = %q, want %q", got.Error, errorBadRequest)
			}
		})
	}
}

func TestABodyThatIsNotJSONIs400(t *testing.T) {
	a := testApp(t)
	recorder := a.do(t, http.MethodPost, "/agent/run", "not json", auth(a.issuer.verified))

	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %q)", recorder.Code, recorder.Body.String())
	}
	if got := decode[errorResponse](t, recorder); got.Detail != "body must be JSON" {
		t.Errorf("detail = %q, want %q", got.Detail, "body must be JSON")
	}
}

// --- The outbound leg -------------------------------------------------------

func TestOutboundCallCarriesTheCallerOnlyFromTheInboundContext(t *testing.T) {
	// The Go-specific failure this quickstart is most likely to have, and the
	// one no amount of reading catches: identity.NewHTTPClient reads the token
	// off the request CONTEXT at send time, so an outbound request built with
	// context.Background() -- or an MCP session connected once at startup --
	// silently sends nothing and the CRM reports no user. The tool looks like it
	// works right up to the point someone checks who it ran as.
	//
	// This drives the real account_summary tool against a stand-in MCP server
	// that reports the header it saw, so the whole outbound path is exercised
	// offline: identity client, streamable transport, per-request session.
	const token = "header.payload.signature"

	seen := make(chan string, 2)
	server := mcp.NewServer(&mcp.Implementation{Name: "stand-in-crm", Version: "0.1.0"}, nil)
	mcp.AddTool(server, &mcp.Tool{
		Name:        toolAccountSummary,
		Description: "Report the user token the call arrived with.",
	}, func(_ context.Context, req *mcp.CallToolRequest, _ struct {
		AccountID string `json:"account_id"`
	},
	) (*mcp.CallToolResult, any, error) {
		header := ""
		if req.Extra.Header != nil {
			header = req.Extra.Header.Get(identity.UserTokenHeader)
		}
		seen <- header
		return &mcp.CallToolResult{
			Content: []mcp.Content{&mcp.TextContent{Text: "ok"}},
		}, nil, nil
	})

	mux := http.NewServeMux()
	mux.Handle(mcpProxyPath+mcpServerName, mcp.NewStreamableHTTPHandler(
		func(*http.Request) *mcp.Server { return server }, nil))
	proxy := httptest.NewServer(mux)
	defer proxy.Close()

	// The tool resolves its address per call, so pointing it at the stand-in is
	// a matter of the same environment variable Catalyst sets.
	t.Setenv(envDaprHTTPEndpoint, proxy.URL)
	client := newMCPHTTPClient()

	t.Run("from the inbound context", func(t *testing.T) {
		ctx := identity.ContextWithToken(context.Background(), token)
		if _, err := accountSummary(ctx, client, "ACME-1"); err != nil {
			t.Fatalf("account summary: %v", err)
		}

		want := identity.BearerPrefix + token
		if got := <-seen; got != want {
			t.Errorf("the CRM saw %q, want %q: the caller did not reach the tool call", got, want)
		}
	})

	t.Run("with no inbound caller", func(t *testing.T) {
		// Not an error, and deliberately so: a trigger with no caller -- a cron
		// or a pub/sub message -- goes out unauthenticated, with the header
		// omitted rather than sent empty.
		if _, err := accountSummary(context.Background(), client, "ACME-1"); err != nil {
			t.Fatalf("account summary: %v", err)
		}
		if got := <-seen; got != "" {
			t.Errorf("the CRM saw %q, want no header at all", got)
		}
	})
}

// --- The offline issuer itself ----------------------------------------------

func TestTheIssuerServesAJWKSTheVerifierCanRead(t *testing.T) {
	// The middleware fetches this document over the loopback port the OS picked.
	// If it were malformed every credential-bearing test above would fail as a
	// 503, so this makes the cause legible.
	a := testApp(t)

	response, err := http.Get(a.issuer.config.JWKSURI)
	if err != nil {
		t.Fatalf("fetch jwks: %v", err)
	}
	defer response.Body.Close()

	var document struct {
		Keys []struct {
			Kid string `json:"kid"`
			Alg string `json:"alg"`
			Kty string `json:"kty"`
		} `json:"keys"`
	}
	if err := json.NewDecoder(response.Body).Decode(&document); err != nil {
		t.Fatalf("parse jwks: %v", err)
	}

	if len(document.Keys) != 1 {
		t.Fatalf("jwks has %d keys, want 1", len(document.Keys))
	}
	key := document.Keys[0]
	if key.Kid != localKeyID || key.Alg != "RS256" || key.Kty != "RSA" {
		t.Errorf("jwks key = %+v, want kid=%s alg=RS256 kty=RSA", key, localKeyID)
	}
}
