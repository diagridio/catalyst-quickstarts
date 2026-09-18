package io.diagrid.quickstart.springai.enterpriseidentity;

import com.fasterxml.jackson.annotation.JsonProperty;
import io.diagrid.ai.identity.VerifiedUser;
import io.diagrid.springai.identity.OAuthFilter;
import jakarta.servlet.http.HttpServletRequest;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * The two routes, and the only place this application touches identity at all. Both read the caller
 * through {@link OAuthFilter#verifiedUser(HttpServletRequest)} and can treat it as trustworthy,
 * because an untrustworthy request never reached them: the filter answered it first.
 */
@RestController
public class IdentityController {

  private static final String BAD_REQUEST = "bad_request";

  private static final String NOT_JSON_DETAIL = "body must be JSON";

  private static final String BAD_TASK_DETAIL = "task must be a non-empty string";

  private static final String TASK_FIELD = "task";

  private static final Logger LOG = LoggerFactory.getLogger(IdentityController.class);

  private final ChatClient agent;

  public IdentityController(ChatClient agent) {
    this.agent = agent;
  }

  @GetMapping("/whoami")
  public Identity whoami(HttpServletRequest request) {
    // Present on every request that gets here: the policy is fail-closed.
    return Identity.of(OAuthFilter.verifiedUser(request).orElseThrow());
  }

  @PostMapping("/agent/run")
  public ResponseEntity<?> agentRun(
      HttpServletRequest request, @RequestBody(required = false) Map<String, Object> body) {

    VerifiedUser user = OAuthFilter.verifiedUser(request).orElseThrow();
    LOG.info("[IDENTITY] verified caller subject={} issuer={}", user.subject(), user.issuerId());

    // Validated after authentication, so the same body from an anonymous caller is still a 401.
    Object task = body == null ? null : body.get(TASK_FIELD);
    if (!(task instanceof String text) || text.isBlank()) {
      return ResponseEntity.badRequest().body(new ErrorResponse(BAD_REQUEST, BAD_TASK_DETAIL));
    }

    // The verified subject travels as tool context, not as a message the model could rewrite.
    Map<String, Object> toolContext = AgentToolContext.forCaller(user.subject());
    String answer = agent.prompt().user(text).toolContext(toolContext).call().content();

    List<String> messages = new ArrayList<>();
    messages.add(text);
    messages.addAll(AgentToolContext.transcriptOf(toolContext));
    if (answer != null && !answer.isEmpty()) {
      messages.add(answer);
    }
    return ResponseEntity.ok(new RunResponse(Identity.of(user), messages));
  }

  /** A body Spring could not read as JSON. Only ever reached by a verified caller. */
  @ExceptionHandler(HttpMessageNotReadableException.class)
  public ResponseEntity<ErrorResponse> unreadableBody() {
    return ResponseEntity.status(HttpStatus.BAD_REQUEST)
        .body(new ErrorResponse(BAD_REQUEST, NOT_JSON_DETAIL));
  }

  /**
   * The verified caller, as JSON. Claim names only, never claim values:
   * {@link VerifiedUser#claims()} is a real person's decoded credential.
   */
  public record Identity(
      String subject,
      String tenant,
      @JsonProperty("issuer_id") String issuerId,
      List<String> scopes) {

    static Identity of(VerifiedUser user) {
      // Sorted so the same caller always produces the same body.
      return new Identity(
          user.subject(), user.tenant(), user.issuerId(), user.scopes().stream().sorted().toList());
    }
  }

  /** The {@code POST /agent/run} body: who ran it, and the conversation it produced. */
  public record RunResponse(Identity user, List<String> messages) {
  }

  /** A refusal this application decided, as opposed to the {@code oauth.*} family the filter owns. */
  public record ErrorResponse(String error, String detail) {
  }
}
