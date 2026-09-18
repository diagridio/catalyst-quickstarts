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
 * <p>The CRM is reached through <b>Catalyst's MCP proxy</b>, not directly. That path mints a
 * credential naming both the user and the agent acting for them, so the CRM establishes who is
 * asking for itself rather than believing the agent. Calling the CRM directly would reach the same
 * server with no user attached at all.
 */
@Component
public class CatalystMcpClient {

  static final String MCP_SERVER_NAME = "crm-mcp";

  static final String ACCOUNT_SUMMARY = "account_summary";

  /** Catalyst's MCP proxy path. Reaching the tool through this is what attaches the caller. */
  static final String MCP_PROXY_PATH = "/v1.0/diagrid/mcp/" + MCP_SERVER_NAME;

  /** The key the caller's token travels under, from the request thread to the sending thread. */
  private static final String USER_TOKEN_CONTEXT_KEY = "diagrid.userToken";

  /** Authenticates the agent itself to Catalyst. Unrelated to the calling user. */
  private static final String DAPR_API_TOKEN_HEADER = "dapr-api-token";

  private static final String DAPR_HTTP_ENDPOINT_VARIABLE = "DAPR_HTTP_ENDPOINT";

  private static final String DAPR_API_TOKEN_VARIABLE = "DAPR_API_TOKEN";

  private static final String DEFAULT_DAPR_HTTP_ENDPOINT = "http://localhost:3500";

  private static final ObjectMapper JSON = new ObjectMapper();

  private static final Logger LOG = LoggerFactory.getLogger(CatalystMcpClient.class);

  private final String baseUrl = environment(DAPR_HTTP_ENDPOINT_VARIABLE, DEFAULT_DAPR_HTTP_ENDPOINT);

  /**
   * Built on first use and shared from then on: the offline walkthrough has no MCP server behind
   * it, and the caller is read at send time, so concurrent requests each carry their own.
   */
  private volatile McpSyncClient client;

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
   * Reads the caller on the request thread, where {@link IdentityContext} holds it. An empty
   * context when there is no caller, so the header is omitted rather than sent blank.
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
   * Sets the identity header on the thread the transport actually sends from, where
   * {@code IdentityContext}'s {@code ThreadLocal} may be empty — hence the transport context.
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

  /** The CRM's sentence, unwrapped from the JSON the MCP server serialised it into. */
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
      // Not JSON at all, so pass it on unchanged.
      return text;
    }
  }

  private static String environment(String name, String fallback) {
    String value = System.getenv(name);
    return value == null || value.isEmpty() ? fallback : value;
  }
}
