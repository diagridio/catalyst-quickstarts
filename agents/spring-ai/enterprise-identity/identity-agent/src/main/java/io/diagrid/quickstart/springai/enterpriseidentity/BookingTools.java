package io.diagrid.quickstart.springai.enterpriseidentity;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.model.ToolContext;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

/**
 * The in-process tool, and the one place the substitution is visible.
 *
 * <p>It declares a {@code subject} argument, so the model really does guess one. <b>That guess is
 * overwritten with the verified caller, never compared against it</b> — the model's opinion of who
 * is calling is never part of the decision. Contrast {@link CrmTools#accountSummary}, which takes
 * no subject at all.
 */
@Component
public class BookingTools {

  static final String MY_BOOKINGS = "my_bookings";

  static final String SUBJECT_ARGUMENT = "subject";

  private static final Logger LOG = LoggerFactory.getLogger(BookingTools.class);

  @Tool(name = MY_BOOKINGS, description = "List the bookings that belong to the calling user.")
  public String myBookings(
      @ToolParam(description = "the user whose bookings to list") String subject,
      ToolContext toolContext) {

    // The verified caller, never the argument above.
    String verified = AgentToolContext.verifiedSubject(toolContext);
    LOG.info("[IDENTITY] tool call for subject={}", verified);

    String answer = "Bookings for " + verified + ": "
        + "Grand Ballroom on March 15th, 9AM-1PM; "
        + "Rooftop Terrace on March 22nd, 6PM-11PM.";
    AgentToolContext.record(toolContext, answer);
    return answer;
  }
}
