//go:build !offline

package main

import (
	"errors"

	"github.com/diagridio/go-ai/identity"
)

// errOfflineIssuerNotBuilt reports DIAGRID_QUICKSTART_IDENTITY=local on a
// binary built without the offline issuer, which is every binary this
// quickstart ships.
var errOfflineIssuerNotBuilt = errors.New(
	envIdentityMode + "=" + identityModeLocal + " needs a binary built with `-tags offline`; " +
		"the offline issuer is deliberately not compiled into the image")

// startLocalIssuer refuses to start without the offline issuer.
//
// This is the Go counterpart of keeping a file out of the image. local_identity.go
// swaps the whole identity plane for a self-signed in-process issuer -- an app
// that trusts tokens it minted itself -- and it is fenced off by the `offline`
// build tag rather than by a .dockerignore entry, because in Go a missing
// source file fails the image BUILD rather than failing closed at run time.
//
// The effect is the one the Python sibling gets from .dockerignore, and the
// compiler enforces it: a shipped binary physically cannot mint the tokens it
// would then trust, so setting the variable on a container derived from this
// quickstart fails to start instead of quietly turning authentication off.
func startLocalIssuer(_ []string) (identity.OAuthConfig, error) {
	return identity.OAuthConfig{}, errOfflineIssuerNotBuilt
}
