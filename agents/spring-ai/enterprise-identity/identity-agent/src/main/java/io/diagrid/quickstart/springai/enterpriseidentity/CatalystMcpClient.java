package io.diagrid.quickstart.springai.enterpriseidentity;

import io.diagrid.ai.identity.IdentityContext;
import io.modelcontextprotocol.client.McpClient;
import io.modelcontextprotocol.client.McpSyncClient;
import io.modelcontextprotocol.client.transport.HttpClientStreamableHttpTransport;
import io.modelcontextprotocol.common.McpTransportContext;
import io.modelcontextprotocol.spec.McpSchema;
import java.net.URI;
import java.net.http.HttpRequest;
import java.util.HashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

/**
 * The MCP client behind {@link CrmTools}, and the on-behalf-of hand-off it needs.
 *
 * <p>The CRM is reached through <b>Catalyst's MCP proxy</b>, not directly. That path is what
 * attaches the calling user: Catalyst mints a token naming both the user and the agent acting for
 * them and forwards it to the CRM, which is why the CRM can establish who is asking for itself
 * rather than believing the agent. Calling {@code http://localhost:8007/mcp} would reach the same
 * server with no user attached at all.
 *
 * <p><b>Why this is not the one-liner the Python quickstart gets.</b> There, the identity-aware HTTP
 * client is handed straight to the MCP transport and the SDK decides the header per request. Two
 * things rule that out here:
 *
 * <ul>
 *   <li>{@code HttpClientStreamableHttpTransport.Builder} accepts only an
 *       {@code HttpClient.Builder}, never a pre-built {@code HttpClient}, so
 *       {@code IdentityHttpClient.from(...)}'s client cannot be given to it.
 *   <li>{@code IdentityContext} holds the caller in a {@code ThreadLocal}, and this transport does
 *       not send every request on the thread that asked for the call. A wrapped client would decide
 *       the header on whichever thread happened to send, and the SDK is explicit that the failure
 *       is <em>silent</em>: the call simply goes out with no identity header.
 * </ul>
 *
 * <p>The two approaches also cannot be combined, which is worth knowing before trying:
 * {@code IdentityHttpClient.wrap} clears the identity header and then sets it from the current
 * thread's context, so wrapping the transport's client would <em>strip</em> the header this class
 * set whenever the send happened on a thread holding no caller — the exact requests the hand-off
 * exists to cover.
 *
 * <p>So the quickstart uses the hand-off the SDK prescribes for exactly this case: read the caller
 * while still on the request thread, and set it again on the other side. The MCP SDK has the two
 * seams for it — {@code transportContextProvider} runs on the calling thread, and
 * {@code httpRequestCustomizer} runs wherever the transport sends from — so the token travels
 * between them in the transport context rather than in a {@code ThreadLocal} the sender cannot see.
 * The header name and the scheme still come from the SDK's own constants; what this class adds is
 * the carry across the thread boundary.
 *
 * <p><b>Measured, not assumed.</b> With {@code logging.level.io.diagrid.quickstart.springai=DEBUG}
 * the two log lines below print their threads. For one {@code tools/call}, the capture runs on the
 * calling thread and the send runs on the calling thread for the JSON-RPC {@code POST}s but on a
 * JDK {@code HttpClient-1-Worker-N} for the SSE {@code GET} stream and the post-initialize
 * notification. That mix is the whole argument for doing it this way: a wrapped identity-aware
 * client would have attached the caller to some requests and silently not to others, and which ones
 * is not something an application should have to know.
 */
@Component
public class CatalystMcpClient {

  /** The MCP server name {@code resources/crm-mcp.yaml} registers. */
  static final String MCP_SERVER_NAME = "crm-mcp";

  static final String ACCOUNT_SUMMARY = "account_summary";

  /** Catalyst's MCP proxy path. Reaching the tool through this is what attaches the caller. */
  static final String MCP_PROXY_PATH = "/v1.0/diagrid/mcp/" + MCP_SERVER_NAME;

  /** The key the caller's token travels under, from the request thread to the sending thread. */
  private static final String USER_TOKEN_CONTEXT_KEY = "diagrid.userToken";

  /** Authenticates the agent itself to its own sidecar. Unrelated to the calling user. */
  private static final String DAPR_API_TOKEN_HEADER = "dapr-api-token";

  private static final String DAPR_HTTP_ENDPOINT_VARIABLE = "DAPR_HTTP_ENDPOINT";

  private static final String DAPR_API_TOKEN_VARIABLE = "DAPR_API_TOKEN";

  private static final String DEFAULT_DAPR_HTTP_ENDPOINT = "http://localhost:3500";

  private static final ObjectMapper JSON = new ObjectMapper();

  private static final Logger LOG = LoggerFactory.getLogger(CatalystMcpClient.class);

  private final String baseUrl = environment(DAPR_HTTP_ENDPOINT_VARIABLE, DEFAULT_DAPR_HTTP_ENDPOINT);

  /**
   * Built on first use rather than at startup, and shared from then on.
   *
   * <p>Lazy because the offline walkthrough never calls the CRM at all: there is no Catalyst project
   * behind it and so no MCP server to connect to, and a client built eagerly would fail the
   * application's startup over a tool it will not use. Shared because the caller is read at send
   * time, so concurrent requests each carry their own.
   *
   * <p><b>One session, not one per call, and that differs from the Python reference</b>, which opens
   * a fresh MCP session inside every tool call. The session here is established by whichever caller
   * happens to reach the CRM first. It is still identity-correct: Catalyst's proxy and the CRM both
   * establish the on-behalf-of identity from the per-request header rather than from the session --
   * the CRM's context extractor runs on each inbound request -- so nothing about who is asking is
   * carried by the connection. Reconnecting per call would add an initialize round trip to every
   * tool call and buy nothing.
   */
  private volatile McpSyncClient client;

  /** The CRM's summary of an account, fetched as the user who invoked the agent. */
  String accountSummary(String accountId) {
    McpSchema.CallToolResult answer = client().callTool(McpSchema.CallToolRequest.builder(ACCOUNT_SUMMARY)
        .arguments(Map.of(CrmTools.ACCOUNT_ID_ARGUMENT, accountId))
        .build());
    return firstText(answer);
  }

  private McpSyncClient client() {
    McpSyncClient current = client;
    if (current != null) {
      return current;
    }
    synchronized (this) {
      if (client == null) {
        client = connect();
      }
      return client;
    }
  }

  private McpSyncClient connect() {
    LOG.info("Connecting to {} through Catalyst's MCP proxy at {}{}",
        MCP_SERVER_NAME, baseUrl, MCP_PROXY_PATH);
    HttpClientStreamableHttpTransport transport = HttpClientStreamableHttpTransport.builder(baseUrl)
        .endpoint(MCP_PROXY_PATH)
        .httpRequestCustomizer(CatalystMcpClient::attachCaller)
        .build();
    McpSyncClient connected = McpClient.sync(transport)
        .transportContextProvider(CatalystMcpClient::captureCaller)
        .build();
    connected.initialize();
    return connected;
  }

  /**
   * Reads the caller on the thread that asked for the tool call — the request thread.
   *
   * <p>Spring AI runs tool calls synchronously inside {@code ChatClient.call()}, so this is still
   * the servlet thread the filter set the token on. An empty context is returned when there is no
   * caller, which is not an error: a downstream service can tell "no user" from "a user with a
   * blank credential", so the header is omitted rather than sent empty.
   */
  static McpTransportContext captureCaller() {
    String token = IdentityContext.currentUserToken();
    LOG.debug("capturing the caller on thread {}", Thread.currentThread().getName());
    if (token == null || token.isEmpty()) {
      return McpTransportContext.EMPTY;
    }
    Map<String, Object> context = new HashMap<>();
    context.put(USER_TOKEN_CONTEXT_KEY, token);
    return McpTransportContext.create(context);
  }

  /**
   * Sets the identity header on the thread the transport actually sends from.
   *
   * <p>The token comes out of the transport context rather than out of {@code IdentityContext},
   * because some of these sends run on a JDK {@code HttpClient} worker thread where that
   * {@code ThreadLocal} is empty.
   */
  static void attachCaller(
      HttpRequest.Builder request, String method, URI endpoint, String body,
      McpTransportContext transportContext) {

    LOG.debug("sending {} {} on thread {}", method, endpoint, Thread.currentThread().getName());
    String apiToken = environment(DAPR_API_TOKEN_VARIABLE, "");
    if (!apiToken.isEmpty()) {
      request.header(DAPR_API_TOKEN_HEADER, apiToken);
    }
    Object token = transportContext == null ? null : transportContext.get(USER_TOKEN_CONTEXT_KEY);
    if (token instanceof String raw && !raw.isEmpty()) {
      request.header(IdentityContext.USER_TOKEN_HEADER, IdentityContext.BEARER_PREFIX + raw);
    }
  }

  /**
   * The CRM's sentence, as prose rather than as the JSON the MCP server wrapped it in.
   *
   * <p>A tool returning a String has it serialised before it travels, so it arrives quoted and
   * escaped. Without decoding, the quotes would end up in the agent's own answer and in the
   * {@code messages} array the README documents.
   */
  private static String firstText(McpSchema.CallToolResult result) {
    for (McpSchema.Content content : result.content()) {
      if (content instanceof McpSchema.TextContent text) {
        return unquote(text.text());
      }
    }
    return "";
  }

  private static String unquote(String text) {
    try {
      Object decoded = JSON.readValue(text, Object.class);
      return decoded instanceof String prose ? prose : text;
    } catch (RuntimeException e) {
      // Not JSON at all, which is the most useful thing to pass on for a result this client knows
      // nothing about.
      return text;
    }
  }

  private static String environment(String name, String fallback) {
    String value = System.getenv(name);
    return value == null || value.isEmpty() ? fallback : value;
  }
}
