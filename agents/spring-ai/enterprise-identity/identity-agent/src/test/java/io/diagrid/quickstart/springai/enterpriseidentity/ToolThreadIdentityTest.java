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
 * The precondition the outbound leg rests on: the caller's credential is readable on the thread a
 * tool runs on.
 *
 * <p>Spring AI decides where a tool call runs, and {@link IdentityContext} is a
 * {@code ThreadLocal} that {@link OAuthFilter} sets on the request thread. If tool calls ever moved
 * to a pool of their own, the call to the CRM would go out with no identity header and the CRM
 * would answer for {@code <no user identity>} instead of failing — a silent regression.
 */
@SpringBootTest
class ToolThreadIdentityTest {

  private static LocalIdentityIssuer.LocalIssuer issuer;

  @Autowired
  private WebApplicationContext context;

  @Autowired
  private OAuthFilter filter;

  /** A spy rather than a mock, so the tool still does its real work. */
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

  /** The exact credential, not merely a non-null one: it must be <em>this</em> caller. */
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
