package io.diagrid.quickstart.springai.enterpriseidentity;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.KeyUse;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import io.diagrid.ai.identity.OAuthConfig;
import java.io.IOException;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Collection;
import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * An offline stand-in for the Catalyst identity plane, enabled with
 * {@code DIAGRID_QUICKSTART_IDENTITY=local}. It generates a throwaway RSA key, serves the public
 * half as JWKS on localhost, and logs three credentials, so the 200, 403 and 401 responses are all
 * reachable with no Catalyst project and no identity provider.
 *
 * <p><b>Never a real deployment.</b> The private key lives in this process's memory and the
 * credentials it signs are logged in plain text.
 */
final class LocalIdentityIssuer {

  static final String ISSUER = "https://local-identity.invalid";

  static final String AUDIENCE = "catalyst-quickstart";

  static final String KID = "local-quickstart-key";

  static final String JWKS_PATH = "/jwks.json";

  static final String VERIFIED_SUBJECT = "alice@example.com";

  static final String WRONG_SCOPE_SUBJECT = "bob@example.com";

  static final String EXPIRED_SUBJECT = "carol@example.com";

  static final String TENANT = "local-tenant";

  /** A scope that is not the one the app requires, so the credential verifies and is still refused. */
  private static final String OTHER_SCOPE = "reports.read";

  private static final long LIFETIME_SECONDS = 3600;

  /** Older than the verifier's 120s clock-skew allowance, so {@code oauth.expired} is reachable. */
  private static final long EXPIRED_LIFETIME_SECONDS = -300;

  private static final int RSA_KEY_SIZE = 2048;

  private static final String JSON_CONTENT_TYPE = "application/json";

  private static final Logger LOG = LoggerFactory.getLogger(LocalIdentityIssuer.class);

  private LocalIdentityIssuer() {
  }

  /** A running throwaway issuer: its config, and the three credentials it accepts. */
  record LocalIssuer(OAuthConfig config, String verified, String wrongScope, String expired) {
  }

  private static volatile LocalIssuer started;

  static synchronized LocalIssuer localIssuer(Set<String> requiredScopes) {
    if (started == null) {
      started = buildLocalIssuer(requiredScopes);
    }
    return started;
  }

  private static LocalIssuer buildLocalIssuer(Set<String> requiredScopes) {
    RSAKey key = generateKey();
    String jwksUri = serveJwks(key.toPublicJWK());

    return new LocalIssuer(
        // The trailing `true` is requireAuth: every route stays authenticated offline too.
        new OAuthConfig(requiredScopes, ISSUER, AUDIENCE, jwksUri, true),
        mint(key, VERIFIED_SUBJECT, requiredScopes, LIFETIME_SECONDS),
        mint(key, WRONG_SCOPE_SUBJECT, Set.of(OTHER_SCOPE), LIFETIME_SECONDS),
        mint(key, EXPIRED_SUBJECT, requiredScopes, EXPIRED_LIFETIME_SECONDS));
  }

  static OAuthConfig startLocalIssuer(Set<String> requiredScopes) {
    LocalIssuer issuer = localIssuer(requiredScopes);

    LOG.warn("LOCAL IDENTITY MODE - throwaway keys, never a real deployment");
    LOG.info("JWKS served at {}", issuer.config().jwksUri());
    LOG.info("200 (verified, has {}):", String.join(" ", sorted(requiredScopes)));
    LOG.info("  {}", issuer.verified());
    LOG.info("403 (verifies, wrong scope) oauth.missing_scope:");
    LOG.info("  {}", issuer.wrongScope());
    LOG.info("401 (expired 5 minutes ago) oauth.expired:");
    LOG.info("  {}", issuer.expired());

    return issuer.config();
  }

  private static RSAKey generateKey() {
    try {
      return new RSAKeyGenerator(RSA_KEY_SIZE)
          .keyID(KID)
          .keyUse(KeyUse.SIGNATURE)
          .algorithm(JWSAlgorithm.RS256)
          .generate();
    } catch (JOSEException e) {
      throw new IllegalStateException("could not generate the throwaway issuer's key", e);
    }
  }

  private static String serveJwks(RSAKey publicKey) {
    // JWKSet.toString() emits the unpadded base64url encoding JWKS requires.
    byte[] document = new JWKSet(List.of(publicKey)).toString().getBytes(StandardCharsets.UTF_8);
    HttpServer server;
    try {
      server = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
    } catch (IOException e) {
      throw new UncheckedIOException("could not start the throwaway JWKS endpoint", e);
    }
    server.createContext("/", exchange -> respond(exchange, document));
    server.start();
    // HttpServer's dispatcher thread is not a daemon, so without this the JVM would not exit.
    Runtime.getRuntime().addShutdownHook(new Thread(() -> server.stop(0), "local-issuer-shutdown"));
    return "http://" + InetAddress.getLoopbackAddress().getHostAddress() + ":"
        + server.getAddress().getPort() + JWKS_PATH;
  }

  private static void respond(HttpExchange exchange, byte[] document) throws IOException {
    exchange.getResponseHeaders().set("Content-Type", JSON_CONTENT_TYPE);
    exchange.sendResponseHeaders(200, document.length);
    try (OutputStream body = exchange.getResponseBody()) {
      body.write(document);
    }
  }

  /** RS256 with {@code kid} set, which is how the verifier selects the key. */
  private static String mint(
      RSAKey key, String subject, Set<String> scopes, long lifetimeSeconds) {

    Instant now = Instant.now();
    JWTClaimsSet claims = new JWTClaimsSet.Builder()
        .subject(subject)
        .issuer(ISSUER)
        .audience(AUDIENCE)
        .claim("tid", TENANT)
        .claim("scp", String.join(" ", sorted(scopes)))
        .issueTime(Date.from(now))
        .expirationTime(Date.from(now.plusSeconds(lifetimeSeconds)))
        .build();
    SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(KID).build(), claims);
    try {
      jwt.sign(new RSASSASigner(key));
    } catch (JOSEException e) {
      throw new IllegalStateException("could not sign a throwaway credential", e);
    }
    return jwt.serialize();
  }

  private static Collection<String> sorted(Set<String> scopes) {
    return new TreeSet<>(scopes);
  }
}
