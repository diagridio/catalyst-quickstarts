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
 * <p>{@link BookingTools#myBookings} runs in-process, so it trusts whatever subject the agent hands
 * it. This tool leaves the process, and that changes the trust story: <b>it takes no subject at
 * all</b>. The calling user travels in a token Catalyst mints for this one call, so the CRM
 * establishes who is asking for itself rather than believing the agent. A tool that cannot be told
 * who is calling cannot be lied to about it.
 */
@Component
public class CrmTools {

  /** The tool's argument name, which is what the canned model has to fill in. */
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

    // Logged for the reader watching `diagrid dev run`, and to make the point that the agent knows
    // the caller here and still does not pass it: the identity travels in the token, not in an
    // argument.
    LOG.info("[IDENTITY] tool call for subject={}",
        AgentToolContext.verifiedSubject(toolContext));

    String answer = crm.accountSummary(accountId);
    AgentToolContext.record(toolContext, answer);
    return answer;
  }
}
