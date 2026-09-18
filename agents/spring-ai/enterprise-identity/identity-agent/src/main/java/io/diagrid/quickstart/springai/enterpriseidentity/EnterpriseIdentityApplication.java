package io.diagrid.quickstart.springai.enterpriseidentity;

import io.diagrid.ai.identity.OAuthConfig;
import io.diagrid.springai.identity.OAuthFilter;
import java.util.Set;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

/**
 * The whole Catalyst identity integration is the one {@code @Bean} below.
 *
 * <p>Spring Boot registers any {@code Filter} bean, so every route in this application is
 * authenticated from here on. Note what is absent everywhere else: no {@code io.diagrid} import in
 * the controller, in the tools or in the agent configuration, and nothing in this application reads
 * the {@code X-Diagrid-User-Token} header.
 *
 * <p><b>No {@code diagrid-spring-ai-starter} on the classpath</b>, unlike the three sibling
 * quickstarts in {@code agents/spring-ai}. That starter runs every {@code ChatClient.call()} as a
 * Dapr Workflow; this quickstart demonstrates identity on the synchronous path, where one HTTP
 * request, one model turn and one tool call all happen on the request thread — which is also what
 * makes the caller's identity visible to the outbound call without a hand-off. See
 * {@link AgentConfig}.
 */
@SpringBootApplication
public class EnterpriseIdentityApplication {

  /**
   * Only the offline issuer demands a scope.
   *
   * <p>Scopes come from your identity provider, and a Diagrid login carries
   * {@code openid profile email offline_access} and nothing else, so requiring one on the Catalyst
   * path would answer 403 for everybody. See "On scopes" in the README.
   */
  static final Set<String> LOCAL_REQUIRED_SCOPES = Set.of("agent.invoke");

  /** Opts in to the offline issuer, and so to the in-process tool. See {@link AgentConfig}. */
  static final String IDENTITY_MODE_VARIABLE = "DIAGRID_QUICKSTART_IDENTITY";

  static final String OFFLINE_IDENTITY_MODE = "local";

  /**
   * Which identity plane the application trusts, and so which tool the agent can use.
   *
   * <p>The offline issuer runs with no Catalyst project behind it, so there is no MCP server to
   * reach and the agent calls the in-process tool instead. Against Catalyst the tool call leaves the
   * agent and picks the caller up on the way.
   */
  static boolean offlineIdentity() {
    return OFFLINE_IDENTITY_MODE.equals(System.getenv(IDENTITY_MODE_VARIABLE));
  }

  public static void main(String[] args) {
    SpringApplication.run(EnterpriseIdentityApplication.class, args);
  }

  // --- The entire Catalyst identity integration ------------------------------
  @Bean
  OAuthFilter diagridOAuthFilter() {
    return new OAuthFilter(buildOAuthConfig());
  }
  // ---------------------------------------------------------------------------
  // requireAuth stays at its default true, so every route is authenticated. That is why no health
  // route is exposed and why dev-enterprise-identity.yaml sets enableAppHealthCheck: false — an
  // unauthenticated probe would only ever see the 401. There is no per-path exclusion; requireAuth
  // is application-wide.

  /**
   * The identity policy the filter enforces on every request.
   *
   * <p>Against Catalyst this is one constructor call with no arguments — issuer, audience and JWKS
   * URI are all discovered from Catalyst, so the application configures none of them.
   *
   * <p>To require a scope as well, pass one: {@code new OAuthConfig(Set.of("reports.read"))}
   * answers {@code 403} for any verified caller without it. That needs an identity provider issuing
   * the scope, which is why the walkthrough does not use it.
   *
   * <p>{@code DIAGRID_QUICKSTART_IDENTITY=local} swaps in a throwaway offline issuer so the 200,
   * 403 and 401 responses are all reachable with no Catalyst project and no identity provider at
   * all. See {@link LocalIdentityIssuer}.
   */
  static OAuthConfig buildOAuthConfig() {
    if (offlineIdentity()) {
      return LocalIdentityIssuer.startLocalIssuer(LOCAL_REQUIRED_SCOPES);
    }
    return new OAuthConfig();
  }
}
