package io.diagrid.quickstart.springai.enterpriseidentity;

import static io.diagrid.quickstart.springai.enterpriseidentity.InboundIdentityTest.bearer;
import static io.diagrid.quickstart.springai.enterpriseidentity.InboundIdentityTest.body;
import static io.diagrid.quickstart.springai.enterpriseidentity.InboundIdentityTest.taskBody;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import io.diagrid.ai.identity.IdentityContext;
import io.diagrid.springai.identity.OAuthFilter;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

/**
 * The thesis of the whole quickstart: the tool answers for the caller the filter verified, never
 * for the subject the model asked about.
 *
 * <p>Asserted end to end through the application, and directly against the tool with a context
 * naming a third subject, which proves the substitution lives in the tool and not the controller.
 */
@SpringBootTest
class SubjectSubstitutionTest {

  private static final String TOOL_ANSWER_PREFIX = "Bookings for ";

  /** A third subject, so the direct case cannot pass by agreeing with the issuer's. */
  private static final String OTHER_SUBJECT = "dave@example.com";

  private static LocalIdentityIssuer.LocalIssuer issuer;

  @Autowired
  private WebApplicationContext context;

  @Autowired
  private OAuthFilter filter;

  @Autowired
  private BookingTools bookingTools;

  private MockMvc mockMvc;

  @BeforeAll
  static void offlineIssuer() {
    issuer = LocalIdentityIssuer.localIssuer(EnterpriseIdentityApplication.LOCAL_REQUIRED_SCOPES);
  }

  @BeforeEach
  void buildMockMvc() {
    mockMvc = MockMvcBuilders.webAppContextSetup(context).addFilters(filter).build();
  }

  /** The model asks for {@code someone@example.com}; the reply names the verified caller. */
  @Test
  void theToolAnswersForTheVerifiedCallerNotTheModelGuess() throws Exception {
    MvcResult result = mockMvc.perform(post("/agent/run")
        .header(IdentityContext.USER_TOKEN_HEADER, bearer(issuer.verified()))
        .contentType(MediaType.APPLICATION_JSON)
        .content(taskBody())).andReturn();

    assertThat(result.getResponse().getStatus()).isEqualTo(200);
    Map<String, Object> response = body(result);
    String raw = result.getResponse().getContentAsString();

    assertThat(((Map<?, ?>) response.get("user")).get("subject"))
        .isEqualTo(LocalIdentityIssuer.VERIFIED_SUBJECT);
    assertThat(response.get("messages")).isEqualTo(List.of(
        "What bookings do I have?",
        TOOL_ANSWER_PREFIX + LocalIdentityIssuer.VERIFIED_SUBJECT
            + ": Grand Ballroom on March 15th, 9AM-1PM; "
            + "Rooftop Terrace on March 22nd, 6PM-11PM.",
        "You have two bookings: the Grand Ballroom on March 15th (9AM-1PM) and "
            + "the Rooftop Terrace on March 22nd (6PM-11PM)."));
    assertThat(raw)
        .as("the model's guessed subject reached the response, so the tool stopped "
            + "substituting the verified subject")
        .doesNotContain(CannedChatModel.MODEL_GUESSED_SUBJECT);
  }

  /** The tool called directly: the argument is the model's own guess, and is still ignored. */
  @Test
  void substitutionHappensInTheToolNotInTheHandler() {
    ToolContext toolContext =
        new ToolContext(AgentToolContext.forCaller(OTHER_SUBJECT));

    String answer = bookingTools.myBookings(CannedChatModel.MODEL_GUESSED_SUBJECT, toolContext);

    assertThat(answer).contains(OTHER_SUBJECT);
    assertThat(answer).doesNotContain(CannedChatModel.MODEL_GUESSED_SUBJECT);
  }

  /** A missing context subject must not fall back to the model's argument. */
  @Test
  void anUnconfiguredSubjectDoesNotSilentlyBecomeTheModelGuess() {
    ToolContext empty = new ToolContext(Map.of());

    String answer = bookingTools.myBookings(CannedChatModel.MODEL_GUESSED_SUBJECT, empty);

    assertThat(answer).doesNotContain(CannedChatModel.MODEL_GUESSED_SUBJECT);
    assertThat(answer).startsWith(TOOL_ANSWER_PREFIX + ":");
  }
}
