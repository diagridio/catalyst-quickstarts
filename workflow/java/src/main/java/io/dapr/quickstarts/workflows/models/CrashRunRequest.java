package io.dapr.quickstarts.workflows.models;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Request body of {@code POST /crash/run}: the instance id the caller owns, and the reference. */
public class CrashRunRequest {

  @JsonProperty("id")
  private String id;

  // The reference the confirmation code is derived from. Defaulted so the documented
  // body can be shortened to just the id.
  @JsonProperty("reference")
  private String reference = "ABC123";

  // Seconds after scheduling at which the app kills ITSELF, so the crash needs neither a
  // second caller nor a human racing the slow activity's window.
  //
  // Optional, and null means today's behaviour exactly: nothing is armed and you crash the
  // app yourself with POST /crash/kill from another terminal. Ignored when the call attaches
  // to an existing instance, because a re-issue is how you collect the result of a run that
  // survived, and killing the app again would put that result out of reach.
  //
  // Integer rather than int: a primitive would default to 0 and be indistinguishable from an
  // absent field, which is the one distinction this has to make.
  @JsonProperty("kill_after_seconds")
  private Integer killAfterSeconds;

  public String getId() {
    return id;
  }

  public void setId(String id) {
    this.id = id;
  }

  public String getReference() {
    return reference;
  }

  public void setReference(String reference) {
    this.reference = reference;
  }

  public Integer getKillAfterSeconds() {
    return killAfterSeconds;
  }

  public void setKillAfterSeconds(Integer killAfterSeconds) {
    this.killAfterSeconds = killAfterSeconds;
  }

  @Override
  public String toString() {
    return "CrashRunRequest [id=" + id + ", reference=" + reference
        + ", killAfterSeconds=" + killAfterSeconds + "]";
  }

}
