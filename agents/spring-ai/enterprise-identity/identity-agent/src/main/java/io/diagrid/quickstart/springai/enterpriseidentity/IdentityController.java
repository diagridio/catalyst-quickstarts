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
 * The two routes, and the only place this application touches identity at all.
 *
 * <p>Both read the caller through {@link OAuthFilter#verifiedUser(HttpServletRequest)} and can treat
 * it as trustworthy, because an untrustworthy request never reached them: the filter answered it
 * first. Neither route is exempt — {@code requireAuth} is application-wide, which is why there is no
 * health endpoint.
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

  /**
   * Who Catalyst says is calling. No model turn, so the 401/200 contrast is free.
   */
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

    // Validated after authentication, so a bad body from a verified caller is a 400 while the same
    // body from an anonymous one is still a 401.
    Object task = body == null ? null : body.get(TASK_FIELD);
    if (!(task instanceof String text) || text.isBlank()) {
      return ResponseEntity.badRequest().body(new ErrorResponse(BAD_REQUEST, BAD_TASK_DETAIL));
    }

    // The verified subject travels as tool context, not as a message the model could rewrite. The
    // transcript travels with it because ChatClient.call() hands back only the final assistant
    // message; see AgentToolContext.
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

  /**
   * A body Spring could not read as JSON.
   *
   * <p>The filter runs before this, so an unreadable body from an anonymous caller is still a 401 —
   * this handler is only ever reached by a verified one.
   */
  @ExceptionHandler(HttpMessageNotReadableException.class)
  public ResponseEntity<ErrorResponse> unreadableBody() {
    return ResponseEntity.status(HttpStatus.BAD_REQUEST)
        .body(new ErrorResponse(BAD_REQUEST, NOT_JSON_DETAIL));
  }

  /**
   * The verified caller, as JSON.
   *
   * <p>Claim names only, never claim values: {@link VerifiedUser#claims()} is a real person's
   * decoded credential, and echoing it back would leak whatever the identity provider chose to put
   * there.
   *
   * <p>The scopes are sorted here rather than taken in the order they arrive, so the body is the
   * same in every Diagrid SDK for the same token. See {@link #of}.
   */
  public record Identity(
      String subject,
      String tenant,
      @JsonProperty("issuer_id") String issuerId,
      List<String> scopes) {

    static Identity of(VerifiedUser user) {
      // Sorted, and not the set's own iteration order: VerifiedUser.scopes() is a LinkedHashSet
      // that preserves the order the credential listed them in, so two tokens carrying the same
      // scopes in a different order would otherwise produce two different response bodies for the
      // same caller.
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
