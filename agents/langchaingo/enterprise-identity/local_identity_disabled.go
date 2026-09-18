//go:build !offline

package main

import (
	"errors"

	"github.com/diagridio/go-ai/identity"
)

var errOfflineIssuerNotBuilt = errors.New(
	envIdentityMode + "=" + identityModeLocal + " needs a binary built with `-tags offline`; " +
		"the offline issuer is deliberately not compiled into the image")

// startLocalIssuer refuses to start without the offline issuer, which the
// `offline` build tag alone compiles in. A shipped binary therefore cannot mint
// credentials it would then trust: setting the variable on a container fails to
// start rather than disabling authentication.
func startLocalIssuer(_ []string) (identity.OAuthConfig, error) {
	return identity.OAuthConfig{}, errOfflineIssuerNotBuilt
}
