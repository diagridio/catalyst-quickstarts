package io.diagrid.quickstart.springai.enterpriseidentity;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The agent: an ordinary Spring AI {@link ChatClient} and the tool it is offered.
 *
 * <p><b>This is where the synchronous path is guaranteed.</b> The client is built from the injected
 * {@code ChatClient.Builder} with no {@code diagrid-spring-ai-starter} on the classpath, so no
 * {@code DurableAdvisor} attaches and nothing here runs as a Dapr Workflow. A reader comparing this
 * against the {@code event-planner} sibling will find the durability dependency missing, and this is
 * the file that says why: the point of this quickstart is where identity enters and how far it
 * travels, and every hop happens on the request thread — which is also what lets the caller's
 * identity reach the outbound MCP call. See {@link CatalystMcpClient}.
 *
 * <p>Nothing in this class is Diagrid-specific, which is the point. The same agent runs unchanged
 * off Catalyst, just without a verified caller to run it for.
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

  /**
   * The one tool the agent gets, chosen by which identity plane the application trusts.
   *
   * <p>The offline issuer has no Catalyst project behind it, so it cannot reach an MCP server;
   * {@code my_bookings} keeps the whole walkthrough runnable there. Against Catalyst the tool call
   * leaves the process and picks the caller up on the way.
   *
   * <p>Named on the client rather than discovered from the application context, which is plain
   * Spring AI: without the diagrid starter nothing rediscovers {@code @Tool} beans, and a tool an
   * agent may call is a tool the application named.
   */
  private static Object tools(BookingTools bookingTools, CrmTools crmTools) {
    if (EnterpriseIdentityApplication.offlineIdentity()) {
      LOG.info("Offline identity mode: the agent calls the in-process my_bookings tool, so the "
          + "on-behalf-of leg to the CRM does not appear. See the README's offline section.");
      return bookingTools;
    }
    return crmTools;
  }
}
