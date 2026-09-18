package io.diagrid.quickstart.springai.crm;

import io.modelcontextprotocol.common.McpTransportContext;
import io.modelcontextprotocol.server.McpSyncServerExchange;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Locale;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.mcp.McpToolUtils;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

/**
 * The CRM's one tool: summarise an account, and report who the CRM is answering.
 *
 * <p>This application has no identity dependency and verifies nothing. Catalyst verified the caller
 * before this process was reached and minted the on-behalf-of token that arrives here, so the only
 * thing left to do is decode the claims in order to show them.
 */
@Component
public class CrmTools {

  /** The header Catalyst puts the on-behalf-of token in. Lower-cased, as HTTP delivers it. */
  static final String USER_TOKEN_HEADER = "x-diagrid-user-token";

  /** Where {@code CrmServerApplication} parks the header for the tool to read. */
  static final String USER_TOKEN_CONTEXT_KEY = "diagrid.userToken";

  private static final String BEARER_PREFIX = "bearer ";

  /** The {@code sub} of the user the call is for. */
  private static final String SUBJECT_CLAIM = "sub";

  /** The delegation claim: {@code act.sub} is the agent acting for that user. */
  private static final String ACTOR_CLAIM = "act";

  private static final String NO_USER = "<no user identity>";

  private static final String NO_AGENT = "<no agent>";

  private static final ObjectMapper JSON = new ObjectMapper();

  private static final Logger LOG = LoggerFactory.getLogger(CrmTools.class);

  @Tool(name = "account_summary",
      description = "Summarise a CRM account, and report who the CRM is answering.")
  public String accountSummary(
      @ToolParam(description = "the CRM account to summarise") String accountId,
      ToolContext toolContext) {

    Map<String, Object> claims = callingUser(toolContext);
    String user = claims.getOrDefault(SUBJECT_CLAIM, NO_USER).toString();
    String agent = claims.get(ACTOR_CLAIM) instanceof Map<?, ?> actor && actor.get(SUBJECT_CLAIM) != null
        ? actor.get(SUBJECT_CLAIM).toString()
        : NO_AGENT;

    LOG.info("account_summary({}) for user={} via agent={}", accountId, user, agent);
    return "Account " + accountId + ": 3 open opportunities, $120k pipeline. "
        + "Served to user=" + user + " via agent=" + agent + ".";
  }

  /**
   * The calling user, read from the token Catalyst minted for this request.
   *
   * <p><b>Decoded, never verified, and that is correct here.</b> Catalyst checked the signature
   * before the request arrived; re-checking it would mean this application knowing Catalyst's key
   * material, which is exactly the coupling the proxy exists to remove. Nothing in the response is
   * an authorization decision — a CRM that made one would verify.
   */
  @SuppressWarnings("unchecked")
  private static Map<String, Object> callingUser(ToolContext toolContext) {
    String raw = rawToken(toolContext);
    String token = raw.toLowerCase(Locale.ROOT).startsWith(BEARER_PREFIX)
        ? raw.substring(BEARER_PREFIX.length())
        : raw;
    String[] parts = token.split("\\.");
    if (parts.length < 2) {
      return Map.of();
    }
    try {
      // Base64url without padding, which is how a JWS segment is encoded.
      byte[] payload = Base64.getUrlDecoder().decode(parts[1]);
      return JSON.readValue(new String(payload, StandardCharsets.UTF_8), Map.class);
    } catch (RuntimeException e) {
      LOG.warn("could not decode the user token that arrived with this call", e);
      return Map.of();
    }
  }

  /**
   * The raw header value, out of the MCP transport context.
   *
   * <p>Put there by {@code CrmServerApplication}'s context extractor, which runs on the thread that
   * received the HTTP request. This tool may not be running on that thread, so the servlet request
   * is not reachable from here.
   */
  private static String rawToken(ToolContext toolContext) {
    McpSyncServerExchange exchange = McpToolUtils.getMcpExchange(toolContext).orElse(null);
    if (exchange == null) {
      return "";
    }
    McpTransportContext transportContext = exchange.transportContext();
    Object raw = transportContext == null ? null : transportContext.get(USER_TOKEN_CONTEXT_KEY);
    return raw instanceof String value ? value : "";
  }
}
