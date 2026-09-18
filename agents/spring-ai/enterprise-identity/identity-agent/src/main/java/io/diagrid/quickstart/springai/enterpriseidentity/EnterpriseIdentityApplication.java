package io.diagrid.quickstart.springai.enterpriseidentity;

import io.diagrid.ai.identity.OAuthConfig;
import io.diagrid.springai.identity.OAuthFilter;
import java.util.Set;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

/**
 * The whole Catalyst identity integration is the one {@code @Bean} below: Spring Boot registers any
 * {@code Filter} bean, so every route is authenticated from here on. Note what is absent everywhere
 * else — no {@code io.diagrid} import in the controller, the tools or the agent configuration, and
 * nothing in this application reads the {@code X-Diagrid-User-Token} header.
 */
@SpringBootApplication
public class EnterpriseIdentityApplication {

  /** Only the offline issuer demands a scope. See "On scopes" in the README. */
  static final Set<String> LOCAL_REQUIRED_SCOPES = Set.of("agent.invoke");

  static final String IDENTITY_MODE_VARIABLE = "DIAGRID_QUICKSTART_IDENTITY";

  static final String OFFLINE_IDENTITY_MODE = "local";

  static boolean offlineIdentity() {
    return OFFLINE_IDENTITY_MODE.equals(System.getenv(IDENTITY_MODE_VARIABLE));
  }

  public static void main(String[] args) {
    SpringApplication.run(EnterpriseIdentityApplication.class, args);
  }

  @Bean
  OAuthFilter diagridOAuthFilter() {
    return new OAuthFilter(buildOAuthConfig());
  }

  /**
   * The identity policy the filter enforces on every request. Against Catalyst this is one
   * no-argument constructor: issuer, audience and JWKS URI are all discovered.
   * {@code DIAGRID_QUICKSTART_IDENTITY=local} swaps in a throwaway offline issuer instead.
   */
  static OAuthConfig buildOAuthConfig() {
    if (offlineIdentity()) {
      return LocalIdentityIssuer.startLocalIssuer(LOCAL_REQUIRED_SCOPES);
    }
    return new OAuthConfig();
  }
}
