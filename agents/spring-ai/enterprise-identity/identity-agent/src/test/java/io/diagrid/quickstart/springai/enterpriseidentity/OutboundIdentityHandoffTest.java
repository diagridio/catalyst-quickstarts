package io.diagrid.quickstart.springai.enterpriseidentity;

import static org.assertj.core.api.Assertions.assertThat;

import io.diagrid.ai.identity.IdentityContext;
import io.modelcontextprotocol.common.McpTransportContext;
import java.net.URI;
import java.net.http.HttpRequest;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

/**
 * The outbound on-behalf-of hand-off, pinned without a Catalyst project.
 *
 * <p>The full outbound leg needs one: a token naming both the user and the agent is minted by
 * Catalyst's MCP proxy, and nothing here can produce one. What <em>is</em> assertable offline is the
 * part that is this quickstart's own code and the part most likely to break silently — carrying the
 * caller from the request thread to the thread the MCP transport sends on. A regression there sends
 * the call with no identity header at all and the CRM answers for {@code <no user identity>} rather
 * than failing, which is precisely the failure a test should catch instead of a reader.
 *
 * <p>The two halves are exercised on two different threads on purpose. Reading the caller on one and
 * setting the header on another is the whole mechanism; a test that did both on one thread would
 * pass against an implementation that simply read the {@code ThreadLocal} at send time.
 */
class OutboundIdentityHandoffTest {

  private static final String TOKEN = "a.caller.token";

  private static final URI ENDPOINT =
      URI.create("http://localhost:3500" + CatalystMcpClient.MCP_PROXY_PATH);

  @AfterEach
  void clearCaller() {
    IdentityContext.clearCurrentToken();
  }

  @Test
  void theCallerCrossesTheThreadBoundary() throws Exception {
    IdentityContext.setCurrentToken(TOKEN);
    McpTransportContext captured = CatalystMcpClient.captureCaller();

    // The sending thread holds no token of its own, which is the situation the hand-off exists for.
    HttpRequest sent = onAnotherThread(() -> {
      assertThat(IdentityContext.currentUserToken()).isNull();
      HttpRequest.Builder request = HttpRequest.newBuilder(ENDPOINT).GET();
      CatalystMcpClient.attachCaller(request, "GET", ENDPOINT, null, captured);
      return request.build();
    });

    assertThat(identityHeader(sent))
        .contains(IdentityContext.BEARER_PREFIX + TOKEN);
  }

  /**
   * No inbound caller is not an error.
   *
   * <p>A cron trigger or a pub/sub delivery has no user, so the call goes out with no identity header
   * rather than an empty one — a downstream service can tell "no user" from "a user with a blank
   * credential". This is also what the offline walkthrough would hit if it ever reached the CRM.
   */
  @Test
  void noCallerSendsNoIdentityHeader() throws Exception {
    McpTransportContext captured = CatalystMcpClient.captureCaller();

    HttpRequest sent = onAnotherThread(() -> {
      HttpRequest.Builder request = HttpRequest.newBuilder(ENDPOINT).GET();
      CatalystMcpClient.attachCaller(request, "GET", ENDPOINT, null, captured);
      return request.build();
    });

    assertThat(identityHeader(sent)).isEmpty();
  }

  /**
   * A stale context must not resurrect a previous caller.
   *
   * <p>Pinned because the capture and the send are separated in time as well as across threads: the
   * header is decided from the context handed to that one call, so clearing the request thread's
   * token after capture does not retroactively change what was captured, and a context captured with
   * no caller stays without one however the request thread changes afterwards.
   */
  @Test
  void theHeaderComesFromTheCapturedContextAndNotFromTheSendingThread() throws Exception {
    McpTransportContext withoutCaller = CatalystMcpClient.captureCaller();

    HttpRequest sent = onAnotherThread(() -> {
      IdentityContext.setCurrentToken("a.different.token");
      try {
        HttpRequest.Builder request = HttpRequest.newBuilder(ENDPOINT).GET();
        CatalystMcpClient.attachCaller(request, "GET", ENDPOINT, null, withoutCaller);
        return request.build();
      } finally {
        IdentityContext.clearCurrentToken();
      }
    });

    assertThat(identityHeader(sent)).isEmpty();
  }

  private static Optional<String> identityHeader(HttpRequest request) {
    List<String> values =
        request.headers().allValues(IdentityContext.USER_TOKEN_HEADER);
    return values.isEmpty() ? Optional.empty() : Optional.of(values.get(0));
  }

  private static <T> T onAnotherThread(Callable<T> work) throws Exception {
    ExecutorService executor = Executors.newSingleThreadExecutor();
    try {
      Future<T> result = executor.submit(work);
      return result.get();
    } finally {
      executor.shutdownNow();
    }
  }
}
