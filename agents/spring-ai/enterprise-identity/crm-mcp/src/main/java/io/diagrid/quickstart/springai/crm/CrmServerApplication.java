package io.diagrid.quickstart.springai.crm;

import io.modelcontextprotocol.common.McpTransportContext;
import io.modelcontextprotocol.json.jackson3.JacksonMcpJsonMapper;
import java.util.Map;
import org.springframework.ai.mcp.server.webmvc.transport.WebMvcStreamableServerTransportProvider;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.web.servlet.function.ServerRequest;
import tools.jackson.databind.json.JsonMapper;

/**
 * A stand-in CRM, exposed over MCP.
 *
 * <p>Its one tool reports the identity the call arrived with. The agent sends no password and no API
 * key, and the CRM still knows whose question it is answering — and which agent asked on their
 * behalf.
 */
@SpringBootApplication
public class CrmServerApplication {

  public static void main(String[] args) {
    SpringApplication.run(CrmServerApplication.class, args);
  }

  /** Exposes {@code account_summary} as an MCP tool. */
  @Bean
  ToolCallbackProvider crmToolCallbacks(CrmTools crmTools) {
    return MethodToolCallbackProvider.builder().toolObjects(crmTools).build();
  }

  /**
   * The MCP endpoint, declared here only so it can be given a context extractor.
   *
   * <p>Spring AI auto-configures this transport provider itself, and this bean replaces that one
   * (the auto-configuration is {@code @ConditionalOnMissingBean}). Everything else about it is the
   * default; the one thing this adds is the extractor below.
   *
   * <p><b>Why an extractor and not a request-scoped lookup.</b> The tool handler does not necessarily
   * run on the servlet thread that received the request — this transport dispatches through
   * Reactor — so reading the header from Spring's request context inside the tool would be correct
   * only by accident. The extractor runs on the receiving thread by construction, and what it puts
   * in the transport context reaches the tool through the MCP exchange. It is the server-side mirror
   * of the hand-off the agent makes on the way out.
   *
   * @param mcpEndpoint the path {@code resources/crm-mcp.yaml} registers with Catalyst
   */
  @Bean
  WebMvcStreamableServerTransportProvider crmTransportProvider(
      JsonMapper jsonMapper,
      @Value("${spring.ai.mcp.server.streamable-http.mcp-endpoint:/mcp}") String mcpEndpoint) {

    return WebMvcStreamableServerTransportProvider.builder()
        .jsonMapper(new JacksonMcpJsonMapper(jsonMapper))
        .mcpEndpoint(mcpEndpoint)
        .contextExtractor(CrmServerApplication::callingUser)
        .build();
  }

  /** Copies the on-behalf-of token off the inbound request, unverified. See {@link CrmTools}. */
  private static McpTransportContext callingUser(ServerRequest request) {
    String raw = request.headers().firstHeader(CrmTools.USER_TOKEN_HEADER);
    return raw == null
        ? McpTransportContext.EMPTY
        : McpTransportContext.create(Map.of(CrmTools.USER_TOKEN_CONTEXT_KEY, raw));
  }
}
