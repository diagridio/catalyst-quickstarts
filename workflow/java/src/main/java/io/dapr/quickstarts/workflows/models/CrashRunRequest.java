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

  @Override
  public String toString() {
    return "CrashRunRequest [id=" + id + ", reference=" + reference + "]";
  }

}
