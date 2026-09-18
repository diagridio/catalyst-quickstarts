package io.diagrid.quickstart.springai.enterpriseidentity;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The agent: an ordinary Spring AI {@link ChatClient} and the tool it is offered.
 *
 * <p>No {@code diagrid-spring-ai-starter} on the classpath, so every hop happens on the request
 * thread — which is what lets the caller's identity reach the outbound MCP call. See
 * {@link CatalystMcpClient}.
 */
@Configuration
public class AgentConfig {

  private static final String SYSTEM = """
      You are an assistant acting for one specific end user.
      Answer the user's question by calling the tool you have been given.
      Never ask the user who they are, and never guess: you are not told who is
      calling, and the application substitutes the verified caller for you.""";

  private static final Logger LOG = LoggerFactory.getLogger(AgentConfig.class);

  @Bean
  ChatClient identityAgent(ChatClient.Builder builder, BookingTools bookingTools, CrmTools crmTools) {
    return builder.defaultSystem(SYSTEM).defaultTools(tools(bookingTools, crmTools)).build();
  }

  /** The one tool the agent gets: offline there is no Catalyst project, and so no MCP server. */
  private static Object tools(BookingTools bookingTools, CrmTools crmTools) {
    if (EnterpriseIdentityApplication.offlineIdentity()) {
      LOG.info("Offline identity mode: the agent calls the in-process my_bookings tool, so the "
          + "on-behalf-of leg to the CRM does not appear. See the README's offline section.");
      return bookingTools;
    }
    return crmTools;
  }
}
