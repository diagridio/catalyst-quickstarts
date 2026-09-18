package io.diagrid.quickstart.springai.enterpriseidentity;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import io.diagrid.ai.identity.IdentityContext;
import io.diagrid.ai.identity.VerifiedUser;
import io.diagrid.springai.identity.OAuthFilter;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.RequestBuilder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;
import tools.jackson.databind.ObjectMapper;

/**
 * The inbound-identity behaviour this quickstart demonstrates: fail closed, then let the verified
 * caller through.
 *
 * <p>{@link LocalIdentityIssuer} stands in for the Catalyst identity plane, so a credential that
 * genuinely verifies is available offline and the 200 and 403 are assertable here. The whole
 * application is started rather than the controller alone because what is under test is the
 * filter's <em>position</em>: that it answers before any of this repository's code runs, on every
 * route.
 */
@SpringBootTest
class InboundIdentityTest {

  private static final String TASK = "What bookings do I have?";

  private static final ObjectMapper JSON = new ObjectMapper();

  private static LocalIdentityIssuer.LocalIssuer issuer;

  @Autowired
  private WebApplicationContext context;

  @Autowired
  private OAuthFilter filter;

  private MockMvc mockMvc;

  @BeforeAll
  static void offlineModeIsSelected() {
    assertThat(EnterpriseIdentityApplication.offlineIdentity())
        .as("run with DIAGRID_QUICKSTART_IDENTITY=local; the pom sets it for the surefire fork")
        .isTrue();
    issuer = LocalIdentityIssuer.localIssuer(EnterpriseIdentityApplication.LOCAL_REQUIRED_SCOPES);
  }

  @BeforeEach
  void buildMockMvc() {
    mockMvc = MockMvcBuilders.webAppContextSetup(context).addFilters(filter).build();
  }

  /** The application-wide rule, checked on both documented routes rather than assumed for one. */
  @Test
  void noCredentialIsRefusedOnEveryRoute() throws Exception {
    for (RequestBuilder request : List.of(
        get("/whoami"),
        post("/agent/run").contentType(MediaType.APPLICATION_JSON).content(taskBody()))) {

      MvcResult result = mockMvc.perform(request).andReturn();

      assertThat(result.getResponse().getStatus()).isEqualTo(401);
      assertThat(body(result)).isEqualTo(Map.of("error", "oauth.missing_token"));
      // An authorization verdict is not cacheable. The header is the filter's, not Spring MVC's.
      assertThat(result.getResponse().getHeader("Cache-Control")).isEqualTo("no-store");
    }
  }

  /** Trimming a blank header value leaves nothing, so it takes the absent-header branch. */
  @ParameterizedTest
  @ValueSource(strings = {"", "   "})
  void anEmptyHeaderIsTreatedAsNoCredential(String value) throws Exception {
    MvcResult result =
        mockMvc.perform(get("/whoami").header(IdentityContext.USER_TOKEN_HEADER, value)).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(401);
    assertThat(body(result)).isEqualTo(Map.of("error", "oauth.missing_token"));
  }

  /** 403, not 401: authentication succeeded and only authorization failed. */
  @Test
  void aCredentialWithoutTheRequiredScopeIs403() throws Exception {
    MvcResult result = mockMvc.perform(get("/whoami").header(
        IdentityContext.USER_TOKEN_HEADER, bearer(issuer.wrongScope()))).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(403);
    assertThat(body(result)).isEqualTo(Map.of("error", "oauth.missing_scope"));
  }

  /** Five minutes stale, because the verifier allows 120s of clock skew. */
  @Test
  void anExpiredCredentialIs401() throws Exception {
    MvcResult result = mockMvc.perform(get("/whoami").header(
        IdentityContext.USER_TOKEN_HEADER, bearer(issuer.expired()))).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(401);
    assertThat(body(result)).isEqualTo(Map.of("error", "oauth.expired"));
  }

  /**
   * The bare {@code "Bearer"} looks like an empty credential and is not one: HTTP strips trailing
   * header whitespace, so the {@code "Bearer "} prefix never matches and the literal itself is
   * taken as the credential — {@code oauth.decode_error}, not {@code oauth.missing_token}.
   */
  @ParameterizedTest
  @ValueSource(strings = {"Bearer not-a-jwt", "Bearer"})
  void aMalformedTokenIsA401(String headerValue) throws Exception {
    MvcResult result = mockMvc
        .perform(get("/whoami").header(IdentityContext.USER_TOKEN_HEADER, headerValue)).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(401);
    assertThat(body(result)).isEqualTo(Map.of("error", "oauth.decode_error"));
  }

  /** Compared whole, so an {@code Identity} that started echoing claim values would fail here. */
  @Test
  void aVerifiedCallerGetsTheDocumentedIdentity() throws Exception {
    MvcResult result = mockMvc.perform(get("/whoami").header(
        IdentityContext.USER_TOKEN_HEADER, bearer(issuer.verified()))).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(200);
    assertThat(body(result)).isEqualTo(Map.of(
        "subject", LocalIdentityIssuer.VERIFIED_SUBJECT,
        "tenant", LocalIdentityIssuer.TENANT,
        "issuer_id", LocalIdentityIssuer.ISSUER,
        "scopes", List.of("agent.invoke")));
  }

  /**
   * Asserted against {@code Identity.of} rather than over HTTP: the offline credential carries a
   * single scope and so could not tell a sorted list from an unsorted one.
   */
  @Test
  void theScopesInTheResponseAreSorted() {
    VerifiedUser user = new VerifiedUser(
        LocalIdentityIssuer.VERIFIED_SUBJECT,
        LocalIdentityIssuer.TENANT,
        new LinkedHashSet<>(List.of("z.write", "a.read")),
        Map.of("sub", LocalIdentityIssuer.VERIFIED_SUBJECT),
        LocalIdentityIssuer.ISSUER);

    assertThat(IdentityController.Identity.of(user).scopes()).containsExactly("a.read", "z.write");
  }

  /**
   * Malformed JWKS would make every credential-bearing test above fail as an opaque 503, so this
   * makes the cause legible. An encoder emitting {@code +}, {@code /} or {@code =} instead of
   * unpadded base64url publishes a key set no verifier will read.
   */
  @Test
  void theIssuerServesAJwksTheVerifierCanRead() throws Exception {
    HttpResponse<String> response = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(5))
        .build()
        .send(HttpRequest.newBuilder(URI.create(issuer.config().jwksUri())).build(),
            HttpResponse.BodyHandlers.ofString());

    Map<String, Object> document = parse(response.body());
    List<?> keys = (List<?>) document.get("keys");
    Map<?, ?> key = (Map<?, ?>) keys.get(0);

    assertThat(key.get("kid")).isEqualTo(LocalIdentityIssuer.KID);
    assertThat(key.get("alg")).isEqualTo("RS256");
    assertThat(key.get("e")).isEqualTo("AQAB");
    assertThat((String) key.get("n")).doesNotContain("=").doesNotContain("+").doesNotContain("/");
  }

  /**
   * Validated after authentication, so the same body from an anonymous caller is still a 401. The
   * last two rows are not JSON objects at all and take the unreadable-body branch instead of the
   * task check.
   */
  @ParameterizedTest
  @CsvSource(delimiter = '|', value = {
      "{}                  | task must be a non-empty string",
      "{\"task\": \"\"}    | task must be a non-empty string",
      "{\"task\": \"   \"} | task must be a non-empty string",
      "{\"task\": 7}       | task must be a non-empty string",
      "[]                  | body must be JSON",
      "not json            | body must be JSON",
  })
  void aTaskThatIsNotANonEmptyStringIs400(String payload, String detail) throws Exception {
    MvcResult result = mockMvc.perform(post("/agent/run")
        .header(IdentityContext.USER_TOKEN_HEADER, bearer(issuer.verified()))
        .contentType(MediaType.APPLICATION_JSON)
        .content(payload)).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(400);
    assertThat(body(result)).isEqualTo(Map.of("error", "bad_request", "detail", detail.trim()));
  }

  static String taskBody() {
    return "{\"task\":\"" + TASK + "\"}";
  }

  static String bearer(String token) {
    return IdentityContext.BEARER_PREFIX + token;
  }

  static Map<String, Object> body(MvcResult result) {
    try {
      return parse(result.getResponse().getContentAsString());
    } catch (java.io.UnsupportedEncodingException e) {
      throw new IllegalStateException(e);
    }
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> parse(String json) {
    return JSON.readValue(json, Map.class);
  }
}
