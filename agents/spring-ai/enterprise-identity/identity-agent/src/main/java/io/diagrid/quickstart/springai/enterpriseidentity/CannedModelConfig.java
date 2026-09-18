package io.diagrid.quickstart.springai.enterpriseidentity;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Condition;
import org.springframework.context.annotation.ConditionContext;
import org.springframework.context.annotation.Conditional;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.type.AnnotatedTypeMetadata;

/** Selects the offline {@link CannedChatModel} unless the reader asked for a real provider. */
@Configuration
public class CannedModelConfig {

  private static final Logger LOG = LoggerFactory.getLogger(CannedModelConfig.class);

  @Bean
  @Conditional(NotOpenAi.class)
  ChatModel cannedChatModel() {
    LOG.info(">>> Using the canned offline model: no API key needed and the answer is always the"
        + " same. Set DIAGRID_QUICKSTART_MODEL=openai (and export OPENAI_API_KEY) for a real"
        + " provider.");
    return new CannedChatModel(EnterpriseIdentityApplication.offlineIdentity());
  }

  /**
   * True unless {@code spring.ai.model.chat} names OpenAI. Case-insensitive, to be the exact
   * complement of Spring AI's own condition: two matching conditions would contribute two
   * {@code ChatModel} beans and the context would not start.
   */
  static final class NotOpenAi implements Condition {

    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
      String chat = context.getEnvironment().getProperty("spring.ai.model.chat", "none");
      return !"openai".equalsIgnoreCase(chat);
    }
  }
}
