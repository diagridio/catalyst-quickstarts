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
 * <p>No Catalyst, no Dapr, no network and no API key. {@link LocalIdentityIssuer} stands in for the
 * Catalyst identity plane: it signs with a throwaway key it generates in-process and serves the
 * public half as JWKS on a loopback port, so a credential that genuinely verifies is available
 * offline. That is what makes the 200 and the 403 assertable here at all — the Robot suite next door
 * can present no credential and therefore asserts only the two 401s.
 *
 * <p><b>Why the whole application is started rather than the controller alone.</b> The thing under
 * test is the filter's <em>position</em>: that it answers before any of this repository's code runs,
 * on every route. A standalone controller test would exercise the handlers with the one component
 * that decides the outcome removed. So {@code @SpringBootTest} brings up the real context — the real
 * {@link OAuthFilter}, configured by the application's own {@code buildOAuthConfig()} — and MockMvc
 * drives it in a real filter chain. {@code DIAGRID_QUICKSTART_IDENTITY=local} is set for the
 * surefire fork in the pom, so that context is the offline one and this test can hold credentials
 * it accepts.
 *
 * <p><b>What is deliberately not tested here: the outbound leg.</b> Carrying the caller onward to an
 * MCP tool needs a Catalyst project, so it is exercised by the README walkthrough. The piece of it
 * that needs no project — the cross-thread hand-off — is pinned in
 * {@link OutboundIdentityHandoffTest}.
 */
@SpringBootTest
class InboundIdentityTest {

  private static final String TASK = "What bookings do I have?";

  private static final ObjectMapper JSON = new ObjectMapper();

  /** The same issuer the application configured itself from. See {@code LocalIdentityIssuer}. */
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
    // addFilters explicitly: the whole point of these tests is that this filter runs, so it is named
    // rather than left to whatever the default filter registration happens to be.
    mockMvc = MockMvcBuilders.webAppContextSetup(context).addFilters(filter).build();
  }

  // --- Fail closed, before any application code runs -------------------------

  /**
   * {@code requireAuth} defaults to true and the filter wraps every route, so this is the
   * application-wide rule the README claims, checked on both documented routes rather than on one
   * and assumed for the other. The exact bodies are the ones the Robot suite asserts against a live
   * Catalyst project.
   */
  @Test
  void noCredentialIsRefusedOnEveryRoute() throws Exception {
    for (RequestBuilder request : List.of(
        get("/whoami"),
        post("/agent/run").contentType(MediaType.APPLICATION_JSON).content(taskBody()))) {

      MvcResult result = mockMvc.perform(request).andReturn();

      assertThat(result.getResponse().getStatus()).isEqualTo(401);
      assertThat(body(result)).isEqualTo(Map.of("error", "oauth.missing_token"));
      // An authorization verdict is not a cacheable response. This header is the filter's, not
      // Spring MVC's, and the README documents it.
      assertThat(result.getResponse().getHeader("Cache-Control")).isEqualTo("no-store");
    }
  }

  /**
   * The README claims "no header, or an empty one" is 401, so both halves are checked.
   * {@code IdentityContext.trimBearer} strips whitespace, so a blank value leaves an empty token and
   * takes the same branch as an absent header.
   */
  @ParameterizedTest
  @ValueSource(strings = {"", "   "})
  void anEmptyHeaderIsTreatedAsNoCredential(String value) throws Exception {
    MvcResult result =
        mockMvc.perform(get("/whoami").header(IdentityContext.USER_TOKEN_HEADER, value)).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(401);
    assertThat(body(result)).isEqualTo(Map.of("error", "oauth.missing_token"));
  }

  /**
   * 403, not 401, and the distinction is the point: authentication succeeded and authorization
   * failed. The credential is signed by the same issuer and has not expired — it simply carries a
   * scope the application does not require.
   */
  @Test
  void aCredentialWithoutTheRequiredScopeIs403() throws Exception {
    MvcResult result = mockMvc.perform(get("/whoami").header(
        IdentityContext.USER_TOKEN_HEADER, bearer(issuer.wrongScope()))).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(403);
    assertThat(body(result)).isEqualTo(Map.of("error", "oauth.missing_scope"));
  }

  /**
   * Five minutes stale, because the verifier allows 120s of clock skew. If
   * {@code LocalIdentityIssuer}'s expired lifetime ever creeps inside that window this returns 200
   * and fails here rather than in a reader's terminal.
   */
  @Test
  void anExpiredCredentialIs401() throws Exception {
    MvcResult result = mockMvc.perform(get("/whoami").header(
        IdentityContext.USER_TOKEN_HEADER, bearer(issuer.expired()))).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(401);
    assertThat(body(result)).isEqualTo(Map.of("error", "oauth.expired"));
  }

  /**
   * A token that is not a well-formed JWS.
   *
   * <p>The code is asserted and not just the status: 401 alone would still pass if a future version
   * routed this through {@code missing_token} or {@code invalid_signature}, and those mean different
   * things to a reader debugging a real credential.
   *
   * <p>The bare {@code "Bearer"} case looks like an empty credential and is not one.
   * {@code BEARER_PREFIX} is {@code "Bearer "} — the trailing space is part of it — and HTTP strips
   * trailing header whitespace, so the prefix never matches and the literal string {@code "Bearer"}
   * is taken as the token. It therefore lands here, among the malformed tokens, rather than on the
   * {@code oauth.missing_token} path an empty header gets. Same status either way, a different code,
   * and that is worth pinning.
   */
  @ParameterizedTest
  @ValueSource(strings = {"Bearer not-a-jwt", "Bearer"})
  void aMalformedTokenIsA401(String headerValue) throws Exception {
    MvcResult result = mockMvc
        .perform(get("/whoami").header(IdentityContext.USER_TOKEN_HEADER, headerValue)).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(401);
    assertThat(body(result)).isEqualTo(Map.of("error", "oauth.decode_error"));
  }

  // --- The verified caller reaches the application ---------------------------

  /**
   * The exact object the README's offline section prints.
   *
   * <p>Compared whole rather than field by field, which is what makes it an assertion about what is
   * <em>absent</em> too: {@code VerifiedUser.claims()} is a real person's decoded credential in a
   * deployment, and a future {@code Identity} that started echoing it back would fail here.
   */
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
   * The scopes in the response body are sorted, whatever order the credential listed them in.
   *
   * <p>Asserted against {@code Identity.of} rather than over HTTP, because the offline issuer's
   * credential carries a single scope and so could not tell a sorted list from an unsorted one. The
   * SDK hands the scopes back in the credential's own order, so without the sort two tokens naming
   * the same scopes in a different order would produce two different bodies for the same caller.
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
   * The JWKS document the filter fetched, pinned.
   *
   * <p>If it were malformed every credential-bearing test above would fail as an opaque 503, so this
   * makes the cause legible. {@code AQAB} is the standard RSA exponent in unpadded base64url; an
   * encoder emitting {@code +}, {@code /} or {@code =} is the classic way to publish a key set no
   * verifier will read.
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

  // --- Request validation ----------------------------------------------------

  /**
   * Validated after authentication, so a bad body from a verified caller is a 400 while the same
   * body from an anonymous one is still a 401.
   *
   * <p>The last two rows are not JSON objects at all — an array, and text that is not JSON — and
   * Spring cannot read either into the handler's parameter, so they take the unreadable-body branch
   * instead of the task check. Both are still {@code 400 bad_request}, which is what the reference
   * quickstart's tests assert about them.
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
