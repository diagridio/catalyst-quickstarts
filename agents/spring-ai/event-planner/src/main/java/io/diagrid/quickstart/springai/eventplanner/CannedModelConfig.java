package io.diagrid.quickstart.springai.eventplanner;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.type.AnnotatedTypeMetadata;

/**
 * Selects the offline {@link CannedChatModel} unless the reader asked for a real provider.
 *
 * <p>Kept out of {@link EventPlannerAgentConfig} on purpose: that class defines the agent and is
 * read as the agent's definition, and a conditional model bean sitting in it would be the second
 * thing that file does.
 */
@Configuration
public class CannedModelConfig {

  private static final Logger LOG = LoggerFactory.getLogger(CannedModelConfig.class);

  @Bean
  @Conditional(NotOpenAi.class)
  ChatModel cannedChatModel() {
    LOG.info(">>> Using the canned offline model: no API key needed and the answer is always the"
        + " same. Set DIAGRID_QUICKSTART_MODEL=openai (and export OPENAI_API_KEY) for a real"
        + " provider.");
    return new CannedChatModel();
  }

  /**
   * True unless {@code spring.ai.model.chat} names OpenAI, which is what
   * {@code application.properties} maps {@code DIAGRID_QUICKSTART_MODEL} onto.
   *
   * <p><b>This has to be the exact complement of Spring AI's own condition, and getting that wrong
   * breaks startup.</b> {@code OpenAiChatAutoConfiguration} is
   * {@code @ConditionalOnProperty(name = "spring.ai.model.chat", havingValue = "openai",
   * matchIfMissing = true)}, and {@code @ConditionalOnProperty} compares with
   * {@code equalsIgnoreCase}. So this must ignore case too: an {@code equals} comparison would make
   * {@code DIAGRID_QUICKSTART_MODEL=OpenAI} satisfy <em>both</em> conditions, and two {@code
   * ChatModel} beans is fatal — the injection points fail with {@code
   * NoUniqueBeanDefinitionException} naming neither the variable the reader set nor the one they
   * meant.
   *
   * <p><b>A {@code Condition} rather than {@code @ConditionalOnExpression}.</b> The property
   * placeholder in an expression is resolved before the string is parsed, so the environment
   * variable's value becomes SpEL source and a value containing a quote fails the context with a
   * parse error — the same class of confusing startup failure this condition exists to avoid. Here
   * the value is read as data and never parsed.
   *
   * <p>The two conditions are exhaustive and mutually exclusive, so exactly one {@code ChatModel}
   * bean always exists for any value. {@code OpenAI} and {@code OPENAI} mean OpenAI, matching what
   * Spring AI itself would do with them; anything else lands on the canned model with a log line
   * naming the variable.
   *
   * <p>Copied deliberately from the {@code crash-recovery} sibling rather than shared: these are two
   * standalone quickstarts a reader clones one of, and a common module between them would be a
   * dependency neither README mentions.
   */
  static final class NotOpenAi implements Condition {

    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
      String chat = context.getEnvironment().getProperty("spring.ai.model.chat", "none");
      return !"openai".equalsIgnoreCase(chat);
    }
  }
}
