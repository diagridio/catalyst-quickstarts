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
 * <p>It declares a {@code subject} argument, so the model really does guess one — the canned model
 * asks for {@code someone@example.com}, who is nobody. The answer is then served for the subject in
 * the tool context, which the handler filled in from the credential the filter verified.
 *
 * <p><b>Substituting beats validating.</b> Comparing the model's guess against the verified subject
 * and refusing a mismatch would look more careful and be worse: it makes the model's opinion of who
 * is calling part of the decision. There is no version of this where that opinion matters, so the
 * guess is overwritten and never consulted.
 *
 * <p>Contrast {@link CrmTools#accountSummary}, which takes no subject at all: it leaves the process,
 * so it cannot be told who is calling and therefore cannot be lied to.
 */
@Component
public class BookingTools {

  static final String MY_BOOKINGS = "my_bookings";

  /** The tool's argument name, which is what the canned model has to fill in. */
  static final String SUBJECT_ARGUMENT = "subject";

  private static final Logger LOG = LoggerFactory.getLogger(BookingTools.class);

  @Tool(name = MY_BOOKINGS, description = "List the bookings that belong to the calling user.")
  public String myBookings(
      @ToolParam(description = "the user whose bookings to list") String subject,
      ToolContext toolContext) {

    // The verified caller, never the argument above. A model can request anybody's bookings; only
    // the verified caller's are ever served.
    String verified = AgentToolContext.verifiedSubject(toolContext);
    LOG.info("[IDENTITY] tool call for subject={}", verified);

    String answer = "Bookings for " + verified + ": "
        + "Grand Ballroom on March 15th, 9AM-1PM; "
        + "Rooftop Terrace on March 22nd, 6PM-11PM.";
    AgentToolContext.record(toolContext, answer);
    return answer;
  }
}
