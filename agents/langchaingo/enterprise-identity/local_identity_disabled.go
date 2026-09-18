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
// The offline issuer in local_identity.go is compiled in by the `offline` build
// tag alone, so a shipped binary cannot mint the credentials it would then
// trust. Setting the variable on a container fails to start rather than
// disabling authentication.
func startLocalIssuer(_ []string) (identity.OAuthConfig, error) {
	return identity.OAuthConfig{}, errOfflineIssuerNotBuilt
}
