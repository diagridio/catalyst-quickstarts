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
 * An offline stand-in for the Catalyst identity plane.
 *
 * <p>Opt in with {@code DIAGRID_QUICKSTART_IDENTITY=local}. It generates a throwaway RSA key, serves
 * the public half as JWKS on localhost, and logs three ready-to-paste credentials so every response
 * this quickstart describes — 200, 403 and 401 — is reachable with no Catalyst project and no
 * identity provider.
 *
 * <p><b>Why it exists.</b> {@code 403 oauth.missing_scope} needs a credential that genuinely
 * verifies. Against real Catalyst you cannot mint one that lacks a scope, and with no issuer
 * configured at all the filter answers {@code 503 oauth.not_configured} instead. This is the only way
 * the scope check is observable. It is the same trade {@link CannedChatModel} makes for the model:
 * free, offline, identical on every run.
 *
 * <p><b>Never a real deployment.</b> The private key lives in this process's memory and the
 * credentials it signs are logged in plain text.
 *
 * <p>Unlike the Python quickstart, whose {@code .dockerignore} keeps the equivalent file out of the
 * image so that setting the variable on a container fails to start rather than quietly disabling
 * authentication, this class compiles into the jar. This repository's Java images copy an
 * already-built {@code target/*.jar}, so no build-context exclusion can reach a class inside it. The
 * guards here are the opt-in variable and the warning below; the README says so plainly rather than
 * implying parity.
 */
final class LocalIdentityIssuer {

  static final String ISSUER = "https://local-identity.invalid";

  static final String AUDIENCE = "catalyst-quickstart";

  static final String KID = "local-quickstart-key";

  static final String JWKS_PATH = "/jwks.json";

  /** The subject of the credential that verifies and carries the required scopes. */
  static final String VERIFIED_SUBJECT = "alice@example.com";

  static final String WRONG_SCOPE_SUBJECT = "bob@example.com";

  static final String EXPIRED_SUBJECT = "carol@example.com";

  static final String TENANT = "local-tenant";

  /** A scope that is not the one the app requires, so the credential verifies and is still refused. */
  private static final String OTHER_SCOPE = "reports.read";

  private static final long LIFETIME_SECONDS = 3600;

  /**
   * diagrid-ai-identity's verifier allows 120s of clock skew, so a credential that expired a minute
   * ago still verifies. Anything demonstrating {@code oauth.expired} has to be older than that.
   */
  private static final long EXPIRED_LIFETIME_SECONDS = -300;

  private static final int RSA_KEY_SIZE = 2048;

  private static final String JSON_CONTENT_TYPE = "application/json";

  private static final Logger LOG = LoggerFactory.getLogger(LocalIdentityIssuer.class);

  private LocalIdentityIssuer() {
  }

  /**
   * A running throwaway issuer: its config, and the credentials it accepts.
   *
   * <p>{@link #startLocalIssuer} returns only the config, because that is all the application needs.
   * The credentials are returned as well so that the tests can present them, which is the only way
   * the 200 and 403 paths are assertable without a Catalyst project.
   *
   * @param config     the policy pointing at this issuer
   * @param verified   carries the required scopes — 200
   * @param wrongScope verifies, carries the wrong scope — 403 {@code oauth.missing_scope}
   * @param expired    carries the required scopes but is stale — 401 {@code oauth.expired}
   */
  record LocalIssuer(OAuthConfig config, String verified, String wrongScope, String expired) {
  }

  /**
   * The one throwaway issuer this process has, started on first request.
   *
   * <p>One per process, not one per caller, and that is the property the tests rely on: the
   * application configures its filter from this issuer, and a test asking for it gets the same
   * instance and so credentials the running application actually accepts. Two issuers would mean the
   * application trusting one key while the credentials in hand were signed by the other — 401
   * {@code oauth.invalid_signature}, for a reason nothing in either file would explain.
   */
  private static volatile LocalIssuer started;

  /**
   * Starts the throwaway issuer and mints the three credentials it accepts, or returns the running
   * one.
   *
   * <p>Logs nothing: {@link #startLocalIssuer} is the entry point that prints the credentials for a
   * reader to paste, and a test that already holds them has no reason to write three JWTs to its own
   * output.
   */
  static synchronized LocalIssuer localIssuer(Set<String> requiredScopes) {
    if (started == null) {
      started = buildLocalIssuer(requiredScopes);
    }
    return started;
  }

  private static LocalIssuer buildLocalIssuer(Set<String> requiredScopes) {
    RSAKey key = generateKey();
    // Port 0: the OS picks a free one, so this never collides with the app.
    String jwksUri = serveJwks(key.toPublicJWK());

    return new LocalIssuer(
        // The trailing `true` is requireAuth, the same value the no-argument constructor uses:
        // every route stays authenticated offline too, which is what makes the 401 reachable here.
        // allowInsecureJwks is deliberately NOT opted into -- that would take the six-argument
        // constructor -- because the verifier already accepts plain http on a loopback JWKS URI,
        // which is what the local sidecar serves keys over as well.
        new OAuthConfig(requiredScopes, ISSUER, AUDIENCE, jwksUri, true),
        mint(key, VERIFIED_SUBJECT, requiredScopes, LIFETIME_SECONDS),
        mint(key, WRONG_SCOPE_SUBJECT, Set.of(OTHER_SCOPE), LIFETIME_SECONDS),
        mint(key, EXPIRED_SUBJECT, requiredScopes, EXPIRED_LIFETIME_SECONDS));
  }

  /**
   * Starts the throwaway issuer, logs its credentials, and returns its config.
   *
   * <p>This is what {@link EnterpriseIdentityApplication} calls. The log lines below are the ones the
   * README's "Run Offline Without a Catalyst Project" block reproduces, so their text is part of the
   * documented output.
   */
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

  /**
   * Publishes the public key as JWKS on a loopback port and returns its URI.
   *
   * <p>{@link JWKSet#toString()} emits the unpadded base64url encoding JWKS requires; hand-rolling
   * the encoding is how the standard exponent ends up as something other than {@code AQAB} and every
   * credential-bearing request then answers an opaque 503.
   */
  private static String serveJwks(RSAKey publicKey) {
    byte[] document = new JWKSet(List.of(publicKey)).toString().getBytes(StandardCharsets.UTF_8);
    HttpServer server;
    try {
      server = HttpServer.create(new InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 0);
    } catch (IOException e) {
      throw new UncheckedIOException("could not start the throwaway JWKS endpoint", e);
    }
    server.createContext("/", exchange -> respond(exchange, document));
    server.start();
    // HttpServer's dispatcher thread is not a daemon, so without this the JVM would not exit on
    // CTRL+C once the web server had stopped.
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

  /**
   * Signs one credential.
   *
   * <p>RS256 with the {@code kid} header set, because the verifier selects the key by {@code kid} and
   * allows only RS256 and ES256. {@code sub}, {@code iss} and {@code exp} are all required; {@code
   * tid} is what {@code VerifiedUser.tenant()} reads, and {@code scp} is the space-delimited scope
   * encoding.
   */
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
