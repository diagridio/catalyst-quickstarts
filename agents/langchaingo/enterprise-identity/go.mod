module github.com/diagridio/catalyst-quickstarts/agents/langchaingo/enterprise-identity

// go-ai v0.2.0 declares go 1.26.4, so this module cannot ask for less.
go 1.26.4

require (
	// The PUBLISHED SDK, and only its identity package. Deliberately NOT
	// goai.NewRunner, go-ai/agent or go-ai/mcp: all three run the agent and its
	// tool calls as Dapr Workflows, and this quickstart is the sync path.
	github.com/diagridio/go-ai v0.2.0

	// The offline throwaway issuer's JWKS document and RS256 signing. Already
	// the SDK's own JWT library, so this adds no second crypto stack.
	github.com/lestrrat-go/jwx/v2 v2.1.6

	// The agent's outbound streamable-HTTP client, and the stand-in CRM's
	// server. Pinned to the version go-ai v0.2.0 itself uses.
	github.com/modelcontextprotocol/go-sdk v1.6.1

	// langchaingo at the llms.Model level: the model interface, the tool
	// declarations and the opt-in OpenAI provider. The framework's durable
	// agent runner is not used here -- see the note on go-ai above.
	github.com/tmc/langchaingo v0.1.15-0.20251029190607-e35755df7084
)

require (
	github.com/decred/dcrd/dcrec/secp256k1/v4 v4.4.0 // indirect
	github.com/dlclark/regexp2 v1.10.0 // indirect
	github.com/goccy/go-json v0.10.3 // indirect
	github.com/google/jsonschema-go v0.4.3 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/lestrrat-go/blackmagic v1.0.3 // indirect
	github.com/lestrrat-go/httpcc v1.0.1 // indirect
	github.com/lestrrat-go/httprc v1.0.6 // indirect
	github.com/lestrrat-go/iter v1.0.2 // indirect
	github.com/lestrrat-go/option v1.0.1 // indirect
	github.com/pkoukk/tiktoken-go v0.1.6 // indirect
	github.com/segmentio/asm v1.2.0 // indirect
	github.com/segmentio/encoding v0.5.4 // indirect
	github.com/yosida95/uritemplate/v3 v3.0.2 // indirect
	golang.org/x/crypto v0.52.0 // indirect
	golang.org/x/oauth2 v0.35.0 // indirect
	golang.org/x/sys v0.45.0 // indirect
)
