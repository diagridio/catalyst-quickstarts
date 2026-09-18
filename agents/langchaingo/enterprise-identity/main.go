// Command identity-agent is a langchaingo agent running on Diagrid Catalyst
// that knows who is calling it and calls its tools as that person.
//
// Two lines of application code buy both halves of that. Note what is absent
// from agent.go and from the tools: no identity import, and nothing that reads
// a header or a credential.
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/diagridio/go-ai/identity"
)

const (
	// defaultAppPort is the port dev-enterprise-identity.yaml declares, used
	// when APP_PORT is unset.
	defaultAppPort = "8006"

	// envAppPort is the port Catalyst forwards inbound calls to.
	envAppPort = "APP_PORT"

	// envIdentityMode opts in to the throwaway offline issuer, and
	// identityModeLocal is the one value that does so. See local_identity.go.
	envIdentityMode   = "DIAGRID_QUICKSTART_IDENTITY"
	identityModeLocal = "local"

	// errorBadRequest is this app's own error code, kept distinct from the
	// oauth.* family the middleware owns: a malformed body is the caller's
	// mistake, not an authorization verdict.
	errorBadRequest = "bad_request"
)

// localRequiredScope is demanded by the offline issuer alone. Scopes come from
// your identity provider, and a Diagrid login carries
// `openid profile email offline_access` and nothing else, so requiring one on
// the Catalyst path would answer 403 for everybody. See "On scopes" in the
// README.
const localRequiredScope = "agent.invoke"

// localRequiredScopes is the offline issuer's policy as the middleware takes
// it. A function rather than a package-level slice so no caller can append to
// the app's own policy.
func localRequiredScopes() []string {
	return []string{localRequiredScope}
}

// identityResponse is the verified caller, as JSON.
//
// Claim names only, never claim values: VerifiedUser.Claims is a real person's
// decoded credential, and echoing it back would leak whatever the identity
// provider chose to put there. That is why there is no Claims field here.
type identityResponse struct {
	Subject  string   `json:"subject"`
	Tenant   string   `json:"tenant"`
	IssuerID string   `json:"issuer_id"`
	Scopes   []string `json:"scopes"`
}

// agentRunResponse is what POST /agent/run returns: who the caller is, and the
// conversation the agent had on their behalf.
type agentRunResponse struct {
	User     identityResponse `json:"user"`
	Messages []string         `json:"messages"`
}

// errorResponse is this app's error envelope. It matches the middleware's
// shape, so a client parses one thing whichever layer refused it.
type errorResponse struct {
	Error  string `json:"error"`
	Detail string `json:"detail,omitempty"`
}

func main() {
	offline := offlineIdentity()

	// Built before the middleware so a misconfigured offline issuer stops the
	// process here rather than answering 503 to every request later.
	oauth, err := buildOAuthConfig(offline)
	if err != nil {
		log.Fatalf("identity configuration: %v", err)
	}

	handler := newHandler(oauth, newAgent(offline))

	addr := "0.0.0.0:" + appPort()
	// The line the README tells a reader to wait for.
	log.Printf("listening on http://%s", addr)
	if err := http.ListenAndServe(addr, handler); err != nil {
		log.Fatalf("serve: %v", err)
	}
}

// --- The entire Catalyst identity integration ------------------------------

// newHandler puts the identity middleware in front of the app's routes.
//
// RequireAuth stays at its default true, so every route is authenticated.
// There is no per-path exclusion.
func newHandler(oauth identity.OAuthConfig, a *agent) http.Handler {
	return identity.Middleware(oauth)(newMux(a))
}

// buildOAuthConfig is the identity policy the middleware enforces on every
// request.
//
// Against Catalyst this is the zero value -- issuer, audience and JWKS URI are
// all discovered from Catalyst, so the app configures none of them.
//
// To require a scope as well, pass one:
// `identity.OAuthConfig{Scopes: []string{"reports.read"}}` answers 403 for any
// verified caller without it. That needs an identity provider issuing the
// scope, which is why the walkthrough does not use it.
//
// DIAGRID_QUICKSTART_IDENTITY=local swaps in a throwaway offline issuer so the
// 200, 403 and 401 responses are all reachable with no Catalyst project and no
// identity provider at all. See local_identity.go.
func buildOAuthConfig(offline bool) (identity.OAuthConfig, error) {
	if offline {
		return startLocalIssuer(localRequiredScopes())
	}
	return identity.OAuthConfig{}, nil
}

// ---------------------------------------------------------------------------

// newMux is the app's two routes. Both read the verified caller from the
// request context, and both may treat it as trustworthy, because an
// untrustworthy request never reached them.
func newMux(a *agent) *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /whoami", whoami)
	mux.HandleFunc("POST /agent/run", agentRun(a))
	return mux
}

// whoami reports who Catalyst says is calling. No model turn, so the 401/200
// contrast is free.
func whoami(w http.ResponseWriter, r *http.Request) {
	user, ok := identity.UserFromContext(r.Context())
	if !ok {
		// Unreachable while RequireAuth is at its default true: the middleware
		// answers 401 before the handler runs.
		writeJSON(w, http.StatusInternalServerError, errorResponse{Error: "no_verified_user"})
		return
	}
	writeJSON(w, http.StatusOK, projectIdentity(user))
}

// agentRun runs the agent for the verified caller.
func agentRun(a *agent) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		user, ok := identity.UserFromContext(r.Context())
		if !ok {
			writeJSON(w, http.StatusInternalServerError, errorResponse{Error: "no_verified_user"})
			return
		}
		log.Printf("[IDENTITY] verified caller subject=%s issuer=%s", user.Subject, user.IssuerID)

		task, problem := decodeTask(r)
		if problem != "" {
			writeJSON(w, http.StatusBadRequest, errorResponse{Error: errorBadRequest, Detail: problem})
			return
		}

		// The verified subject travels as an argument the model never sees, not
		// as a message it could rewrite. The request's context travels with it,
		// which is what carries the caller onward to the MCP tool call.
		messages, err := a.run(r.Context(), task, user.Subject)
		if err != nil {
			log.Printf("agent run failed: %v", err)
			writeJSON(w, http.StatusBadGateway, errorResponse{Error: "agent_failed"})
			return
		}

		writeJSON(w, http.StatusOK, agentRunResponse{
			User:     projectIdentity(user),
			Messages: messages,
		})
	}
}

// decodeTask validates the documented request body, returning the task or the
// detail to report. Validation runs after authentication, so a bad body from a
// verified caller is a 400 while the same body from an anonymous one is still a
// 401.
//
// The body is decoded as `any` so a wrong-shaped body is reported as a bad task
// rather than as unparseable input.
func decodeTask(r *http.Request) (task string, problem string) {
	var body any
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		return "", "body must be JSON"
	}

	const badTask = "task must be a non-empty string"
	object, ok := body.(map[string]any)
	if !ok {
		return "", badTask
	}
	task, ok = object["task"].(string)
	if !ok || strings.TrimSpace(task) == "" {
		return "", badTask
	}
	return task, ""
}

// projectIdentity is the four fields this app chooses to expose from the
// VerifiedUser. See identityResponse for what it deliberately leaves out.
func projectIdentity(user *identity.VerifiedUser) identityResponse {
	scopes := user.Scopes
	if scopes == nil {
		// A JSON array even when the token carried none, so a client parsing
		// the response never has to handle null as well as [].
		scopes = []string{}
	}
	return identityResponse{
		Subject:  user.Subject,
		Tenant:   user.Tenant,
		IssuerID: user.IssuerID,
		Scopes:   scopes,
	}
}

// offlineIdentity reports which identity plane the app trusts, and so which
// tool the agent can use. The offline issuer runs with no Catalyst project
// behind it, so there is no MCP server to reach and the agent calls the
// in-process tool instead. Against Catalyst the tool call leaves the agent and
// picks the caller up on the way.
func offlineIdentity() bool {
	return os.Getenv(envIdentityMode) == identityModeLocal
}

func appPort() string {
	if port := os.Getenv(envAppPort); port != "" {
		return port
	}
	return defaultAppPort
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(body); err != nil {
		// The status and part of the body are already on the wire, so there is
		// nothing left to tell the client.
		log.Printf("write response: %v", err)
	}
}
