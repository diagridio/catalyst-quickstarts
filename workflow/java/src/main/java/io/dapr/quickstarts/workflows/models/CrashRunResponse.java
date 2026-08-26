package io.dapr.quickstarts.workflows.models;

/**
 * Response body of {@code POST /crash/run}. A 200 carries {@code result}; a 202 carries
 * {@code message}, telling the caller to re-issue the same request to attach.
 */
public class CrashRunResponse {

  private String id;
  private String result;
  private String message;

  public CrashRunResponse() {
  }

  public CrashRunResponse(String id, String result, String message) {
    this.id = id;
    this.result = result;
    this.message = message;
  }

  public String getId() {
    return id;
  }

  public void setId(String id) {
    this.id = id;
  }

  public String getResult() {
    return result;
  }

  public void setResult(String result) {
    this.result = result;
  }

  public String getMessage() {
    return message;
  }

  public void setMessage(String message) {
    this.message = message;
  }
}
