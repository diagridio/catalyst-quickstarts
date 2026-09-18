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
 * <p>What is assertable offline is carrying the caller from the request thread to the thread the
 * MCP transport sends on. The two halves run on two threads on purpose: a test that did both
 * on one thread would pass against an implementation that simply read the {@code ThreadLocal} at
 * send time.
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

  /** No inbound caller is not an error: no identity header at all, rather than an empty one. */
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

  /** The header is decided from the captured context, not from what the sending thread holds. */
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
