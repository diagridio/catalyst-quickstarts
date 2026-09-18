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

  @Bean
  ToolCallbackProvider crmToolCallbacks(CrmTools crmTools) {
    return MethodToolCallbackProvider.builder().toolObjects(crmTools).build();
  }

  /**
   * The MCP endpoint, declared only so it can be given a context extractor. An extractor rather
   * than a request-scoped lookup because the tool handler does not necessarily run on the servlet
   * thread that received the request — this transport dispatches through Reactor.
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
