//go:build offline

package main

import (
	"crypto/rand"
	"crypto/rsa"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"slices"
	"strings"
	"time"

	"github.com/lestrrat-go/jwx/v2/jwa"
	"github.com/lestrrat-go/jwx/v2/jwk"
	"github.com/lestrrat-go/jwx/v2/jwt"

	"github.com/diagridio/go-ai/identity"
)

// This file is an offline stand-in for the Catalyst identity plane.
//
// Opt in with DIAGRID_QUICKSTART_IDENTITY=local, on a binary built with
// `-tags offline`. It generates a throwaway RSA key, serves the public half as
// JWKS on localhost, and logs three ready-to-paste credentials so every
// response this quickstart describes -- 200, 403 and 401 -- is reachable with
// no Catalyst project and no identity provider.
//
// 403 oauth.missing_scope needs a credential that verifies but lacks a scope;
// with no issuer configured the middleware answers 503 oauth.not_configured
// instead.
//
// Never a real deployment. The private key lives in this process's memory and
// the credentials it signs are logged in plain text. The `offline` build tag is
// what keeps it out of the shipped image -- see local_identity_disabled.go.

const (
	localIssuerName = "https://local-identity.invalid"
	localAudience   = "catalyst-quickstart"
	localKeyID      = "local-quickstart-key"
	localTenant     = "local-tenant"

	// localTokenLifetime is how long a fresh credential is good for.
	localTokenLifetime = time.Hour

	// expiredTokenLifetime is negative, so the credential it mints expired five
	// minutes before it was issued. The SDK's verifier allows 120s of clock
	// skew, so a credential that expired a minute ago still verifies -- anything
	// demonstrating oauth.expired has to be older than that.
	expiredTokenLifetime = -5 * time.Minute
)

// localIssuer is a running throwaway issuer: its config, and the credentials it
// accepts.
//
// startLocalIssuer returns only the config, because that is all main.go needs.
// The credentials are kept here as well so the tests can present them.
type localIssuer struct {
	config identity.OAuthConfig

	// verified carries the required scopes -> 200.
	verified string

	// wrongScope verifies, and carries the wrong scope -> 403
	// oauth.missing_scope.
	wrongScope string

	// expired carries the required scopes but is stale -> 401 oauth.expired.
	expired string
}

// buildLocalIssuer starts the throwaway issuer and mints the three credentials
// it accepts.
//
// It logs nothing: startLocalIssuer is the entry point that prints the
// credentials for a reader to paste, and a test that already holds them has no
// reason to write three JWTs to its own output.
func buildLocalIssuer(requiredScopes []string) (localIssuer, error) {
	raw, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return localIssuer{}, fmt.Errorf("generate rsa key: %w", err)
	}

	private, err := jwk.FromRaw(raw)
	if err != nil {
		return localIssuer{}, fmt.Errorf("wrap private key: %w", err)
	}
	if err := private.Set(jwk.KeyIDKey, localKeyID); err != nil {
		return localIssuer{}, fmt.Errorf("set kid: %w", err)
	}
	if err := private.Set(jwk.AlgorithmKey, jwa.RS256); err != nil {
		return localIssuer{}, fmt.Errorf("set alg: %w", err)
	}

	jwksURI, err := serveJWKS(private)
	if err != nil {
		return localIssuer{}, err
	}

	mint := func(subject string, scopes []string, lifetime time.Duration) (string, error) {
		return mintToken(private, subject, scopes, lifetime)
	}

	verified, err := mint("alice@example.com", requiredScopes, localTokenLifetime)
	if err != nil {
		return localIssuer{}, err
	}
	wrongScope, err := mint("bob@example.com", []string{"reports.read"}, localTokenLifetime)
	if err != nil {
		return localIssuer{}, err
	}
	expired, err := mint("carol@example.com", requiredScopes, expiredTokenLifetime)
	if err != nil {
		return localIssuer{}, err
	}

	return localIssuer{
		config: identity.OAuthConfig{
			Scopes:   requiredScopes,
			Issuer:   localIssuerName,
			Audience: localAudience,
			JWKSURI:  jwksURI,
		},
		verified:   verified,
		wrongScope: wrongScope,
		expired:    expired,
	}, nil
}

// startLocalIssuer starts the throwaway issuer, logs its credentials, and
// returns its config.
//
// This is what main.go calls. The log lines are the ones the README's
// "## Run Offline Without a Catalyst Project" block reproduces, so their text
// is part of the documented output.
func startLocalIssuer(requiredScopes []string) (identity.OAuthConfig, error) {
	issuer, err := buildLocalIssuer(requiredScopes)
	if err != nil {
		return identity.OAuthConfig{}, err
	}

	scopes := slices.Clone(requiredScopes)
	slices.Sort(scopes)

	log.Printf("LOCAL IDENTITY MODE - throwaway keys, never a real deployment")
	log.Printf("JWKS served at %s", issuer.config.JWKSURI)
	log.Printf("200 (verified, has %s):", strings.Join(scopes, " "))
	log.Printf("  %s", issuer.verified)
	log.Printf("403 (verifies, wrong scope) oauth.missing_scope:")
	log.Printf("  %s", issuer.wrongScope)
	log.Printf("401 (expired 5 minutes ago) oauth.expired:")
	log.Printf("  %s", issuer.expired)

	return issuer.config, nil
}

// serveJWKS publishes the public half of key on a loopback port and returns its
// URI.
//
// Port 0: the OS picks a free one, so this never collides with the app. Plain
// http needs no AllowInsecureJWKS, because the SDK exempts loopback from its
// https-only rule -- there is no path to be on.
func serveJWKS(key jwk.Key) (string, error) {
	public, err := key.PublicKey()
	if err != nil {
		return "", fmt.Errorf("derive public key: %w", err)
	}
	set := jwk.NewSet()
	if err := set.AddKey(public); err != nil {
		return "", fmt.Errorf("add public key: %w", err)
	}
	document, err := json.Marshal(set)
	if err != nil {
		return "", fmt.Errorf("marshal jwks: %w", err)
	}

	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", fmt.Errorf("listen for jwks: %w", err)
	}

	handler := http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(document)
	})
	// No error handling on Serve: the listener is closed only when the process
	// exits, at which point there is nobody left to tell.
	go func() { _ = http.Serve(listener, handler) }()

	return fmt.Sprintf("http://%s/jwks.json", listener.Addr().String()), nil
}

// mintToken signs a credential with the throwaway key. A negative lifetime
// mints one that is already stale, which is how the oauth.expired credential is
// produced.
func mintToken(key jwk.Key, subject string, scopes []string, lifetime time.Duration) (string, error) {
	now := time.Now().UTC()
	sorted := slices.Clone(scopes)
	slices.Sort(sorted)

	token, err := jwt.NewBuilder().
		Subject(subject).
		Issuer(localIssuerName).
		Audience([]string{localAudience}).
		IssuedAt(now).
		Expiration(now.Add(lifetime)).
		Claim("tid", localTenant).
		Claim("scp", strings.Join(sorted, " ")).
		Build()
	if err != nil {
		return "", fmt.Errorf("build token for %s: %w", subject, err)
	}

	signed, err := jwt.Sign(token, jwt.WithKey(jwa.RS256, key))
	if err != nil {
		return "", fmt.Errorf("sign token for %s: %w", subject, err)
	}
	return string(signed), nil
}
