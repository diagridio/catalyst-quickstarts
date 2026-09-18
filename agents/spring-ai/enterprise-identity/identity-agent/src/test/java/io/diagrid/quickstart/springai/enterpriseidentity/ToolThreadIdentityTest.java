package io.diagrid.quickstart.springai.enterpriseidentity;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import io.diagrid.ai.identity.IdentityContext;
import io.diagrid.springai.identity.OAuthFilter;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoSpyBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

/**
 * The precondition the whole outbound leg rests on: the caller's credential is readable on the
 * thread a tool runs on.
 *
 * <p>{@link OutboundIdentityHandoffTest} pins what {@link CatalystMcpClient} does with the token
 * once it holds one. This pins the step before that, which is the easier one to lose because it is
 * not this quickstart's code at all: Spring AI decides where a tool call runs, and
 * {@link IdentityContext} is a {@code ThreadLocal} that {@link OAuthFilter} sets on the request
 * thread. If Spring AI ever ran tool calls on a pool of its own,
 * {@code CatalystMcpClient.captureCaller} would find nothing, the call to the CRM would go out with
 * no identity header, and the CRM would answer for {@code <no user identity>} instead of failing.
 * That is a silent regression, so it gets a test rather than a paragraph.
 *
 * <p>Driven through the real controller and the real {@code ChatClient}, because the thread a tool
 * runs on is decided by that path and by nothing a narrower test could set up. The tool asserted
 * against is the offline one — the mode these tests run in — but the thread it runs on is chosen by
 * Spring AI's tool-calling loop, which does not know or care which tool it is calling.
 */
@SpringBootTest
class ToolThreadIdentityTest {

  private static LocalIdentityIssuer.LocalIssuer issuer;

  @Autowired
  private WebApplicationContext context;

  @Autowired
  private OAuthFilter filter;

  /**
   * A spy rather than a mock: the tool still does its real work, so this test does not quietly
   * become a test of a stub.
   */
  @MockitoSpyBean
  private BookingTools bookingTools;

  private final AtomicReference<String> tokenSeenByTheTool = new AtomicReference<>();

  private MockMvc mockMvc;

  @BeforeAll
  static void offlineIssuer() {
    issuer = LocalIdentityIssuer.localIssuer(EnterpriseIdentityApplication.LOCAL_REQUIRED_SCOPES);
  }

  @BeforeEach
  void recordWhatTheToolThreadHolds() {
    doAnswer(invocation -> {
      tokenSeenByTheTool.set(IdentityContext.currentUserToken());
      return invocation.callRealMethod();
    }).when(bookingTools).myBookings(anyString(), any());
    mockMvc = MockMvcBuilders.webAppContextSetup(context).addFilters(filter).build();
  }

  /**
   * The exact credential, not merely a non-null one.
   *
   * <p>{@code IdentityContext.currentUserToken()} holds the token with the {@code Bearer} prefix
   * already trimmed, which is the form {@code CatalystMcpClient} re-prefixes when it sets the
   * outbound header. Comparing it against the credential this request presented therefore checks
   * both halves of the claim: that a caller is visible to the tool at all, and that it is
   * <em>this</em> caller.
   */
  @Test
  void theCallersCredentialIsReadableOnTheThreadTheToolRunsOn() throws Exception {
    mockMvc.perform(post("/agent/run")
        .header(IdentityContext.USER_TOKEN_HEADER, InboundIdentityTest.bearer(issuer.verified()))
        .contentType(MediaType.APPLICATION_JSON)
        .content(InboundIdentityTest.taskBody()))
        .andReturn();

    assertThat(tokenSeenByTheTool.get())
        .as("the verified caller was not readable on the tool's thread, so an outbound MCP call "
            + "would go out with no identity header and the CRM would answer for nobody")
        .isEqualTo(issuer.verified());
  }
}
