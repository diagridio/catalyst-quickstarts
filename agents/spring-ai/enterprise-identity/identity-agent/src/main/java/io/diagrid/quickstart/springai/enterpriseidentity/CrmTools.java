package io.diagrid.quickstart.springai.enterpriseidentity;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

/**
 * The outbound half: calling a tool as the user.
 *
 * <p>Unlike {@link BookingTools#myBookings}, this tool leaves the process, and <b>takes no subject
 * at all</b>: the calling user travels in a credential Catalyst mints for this one call, so the CRM
 * establishes who is asking for itself rather than believing the agent.
 */
@Component
public class CrmTools {

  static final String ACCOUNT_ID_ARGUMENT = "accountId";

  private static final Logger LOG = LoggerFactory.getLogger(CrmTools.class);

  private final CatalystMcpClient crm;

  public CrmTools(CatalystMcpClient crm) {
    this.crm = crm;
  }

  @Tool(name = CatalystMcpClient.ACCOUNT_SUMMARY,
      description = "Summarise a CRM account. Runs as the user who invoked the agent.")
  public String accountSummary(
      @ToolParam(description = "the CRM account to summarise") String accountId,
      ToolContext toolContext) {

    // The agent knows the caller here and still does not pass it: identity travels in the
    // credential, not in an argument.
    LOG.info("[IDENTITY] tool call for subject={}",
        AgentToolContext.verifiedSubject(toolContext));

    String answer = crm.accountSummary(accountId);
    AgentToolContext.record(toolContext, answer);
    return answer;
  }
}
