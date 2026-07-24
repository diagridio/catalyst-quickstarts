package io.diagrid.quickstart.springai.crashrecovery;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Defines the booking agent as a <b>named {@link ChatClient} bean</b> so it runs under its own
 * per-agent workflow name ({@code spring-ai.crashRecoveryAgent.workflow}) instead of the generic
 * {@code spring-ai.workflow}. The name is assigned at wiring time from the bean name, and it shows up
 * in the Catalyst dashboard / {@code dapr workflow list}.
 *
 * <p>It must be a {@code ChatClient} <em>bean</em> (not a {@code @Component} that holds a client): the
 * durability auto-config registers a per-agent workflow name on the in-process worker for every
 * ChatClient bean, and its bean post-processor attaches the matching per-agent durable advisor.
 *
 * <p>The booking tool ({@link SlowBookingTools}) is a global {@code @Tool} bean, so it is advertised
 * to this agent automatically (and survives a worker restart); this bean wires no tools of its own.
 */
@Configuration
public class CrashRecoveryAgentConfig {

  private static final String SYSTEM = """
      You are a travel booking assistant. Commit the customer's booking using the
      commitReservation tool and report the confirmation code it returns. Call the tool
      exactly once; never invent a confirmation code.""";

  @Bean
  ChatClient crashRecoveryAgent(ChatClient.Builder builder) {
    return builder.defaultSystem(SYSTEM).build();
  }
}
