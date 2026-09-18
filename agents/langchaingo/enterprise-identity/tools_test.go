// Tests for the tools themselves, and for the one property of them the whole
// quickstart rests on: which tool the agent loop substitutes the verified
// caller into.
//
// No build tag, deliberately, so these run in either mode -- `go test ./...`
// as well as `go test -tags offline ./...`. Nothing here needs an issuer or a
// credential: the question is what the tools DECLARE, not who is calling.
package main

import (
	"testing"

	"github.com/tmc/langchaingo/llms"
)

// withSchema is a tool that declares nothing but the given parameters schema,
// which is all takesSubject reads.
func withSchema(parameters any) tool {
	return tool{declaration: llms.Tool{
		Type: "function",
		Function: &llms.FunctionDefinition{
			Name:       "test-tool",
			Parameters: parameters,
		},
	}}
}

// TestSubstitutionFollowsTheDeclaredSchema pins the invariant that makes the
// substitution in agent.callTool trustworthy: a tool is handed the verified
// subject exactly when its declared schema says it takes one.
//
// The two must agree, because the model can only send arguments the schema
// declares. A tool declaring `subject` that the loop did not substitute into
// would be handed the model's guess -- someone@example.com, or any name a real
// provider invented -- and answer for whoever the model named. That is the one
// failure this quickstart exists to rule out.
func TestSubstitutionFollowsTheDeclaredSchema(t *testing.T) {
	cases := []struct {
		name  string
		tools map[string]tool
		// wantSubstituted is the tool in that set whose calling user the loop
		// must override, or empty when the set has none.
		wantSubstituted string
	}{
		{
			// The in-process tool takes the caller as an argument, so it trusts
			// whatever the agent hands it, so the agent must hand it the
			// verified subject.
			name:            "offline",
			tools:           localTools(),
			wantSubstituted: toolMyBookings,
		},
		{
			// The outbound tool takes no subject at all: the caller travels in
			// the token Catalyst mints for the call, so there is nothing to
			// substitute and nothing to lie to.
			name:            "catalyst",
			tools:           catalystTools(),
			wantSubstituted: "",
		},
	}

	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			for name, tl := range test.tools {
				want := name == test.wantSubstituted
				if got := tl.takesSubject(); got != want {
					t.Errorf("tool %q: takesSubject() = %t, want %t", name, got, want)
				}
			}
			if test.wantSubstituted != "" {
				if _, ok := test.tools[test.wantSubstituted]; !ok {
					t.Errorf("tool %q is not in the %s set at all, so the "+
						"substitution it should receive cannot happen",
						test.wantSubstituted, test.name)
				}
			}
		})
	}
}

// TestADeclarationWithNoSubjectIsNotSubstitutedInto guards the derivation
// itself against the shapes a hand-written schema can take, rather than only
// the two the quickstart ships.
func TestADeclarationWithNoSubjectIsNotSubstitutedInto(t *testing.T) {
	cases := []struct {
		name string
		tool tool
		want bool
	}{
		{name: "no declaration at all", tool: tool{}, want: false},
		{
			name: "subject declared",
			tool: withSchema(objectSchema(map[string]any{
				argSubject: map[string]any{"type": "string"},
			}, argSubject)),
			want: true,
		},
		{
			name: "another argument declared",
			tool: withSchema(objectSchema(map[string]any{
				argAccountID: map[string]any{"type": "string"},
			}, argAccountID)),
			want: false,
		},
		{
			// A schema shape this quickstart does not produce. It must read as
			// "declares no subject" rather than panic: the tool is then handed
			// none and answers for nobody, which is the safe direction.
			name: "properties is not an object",
			tool: withSchema(map[string]any{"type": "object", "properties": "nonsense"}),
			want: false,
		},
		{
			// Likewise for a schema handed over as something other than a map,
			// which a generated declaration might be.
			name: "parameters is not a map",
			tool: withSchema("nonsense"),
			want: false,
		},
	}

	for _, test := range cases {
		t.Run(test.name, func(t *testing.T) {
			if got := test.tool.takesSubject(); got != test.want {
				t.Errorf("takesSubject() = %t, want %t", got, test.want)
			}
		})
	}
}
