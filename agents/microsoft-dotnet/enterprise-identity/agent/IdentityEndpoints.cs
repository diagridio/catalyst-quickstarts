using System.Text.Json;
using System.Text.Json.Serialization;
using Diagrid.AI.Identity;

namespace EnterpriseIdentity;

/// <summary>
/// The two routes this quickstart exposes.
/// </summary>
/// <remarks>
/// <para>
/// Separate from Program.cs so the unit tests drive the app's own handlers rather than a copy of
/// them.
/// </para>
/// <para>
/// Both handlers read the verified caller with <c>GetVerifiedUser()</c> and can treat it as
/// trustworthy, because an untrustworthy request never reached them: <c>RequireAuth</c> stays at its
/// default <see langword="true"/>, so <c>OAuthMiddleware</c> refuses a tokenless request first.
/// </para>
/// </remarks>
public sealed class IdentityEndpoints
{
    /// <summary>The error code both bad-request replies carry. Not an SDK <c>oauth.*</c> code.</summary>
    private const string BadRequestCode = "bad_request";

    private IdentityEndpoints()
    {
    }

    /// <summary>
    /// Who Catalyst says is calling.
    /// </summary>
    /// <remarks>
    /// No model turn and no tool, which makes it the cheapest place to see identity on its own —
    /// and makes the 401/200 contrast free.
    /// </remarks>
    /// <param name="context">The verified request.</param>
    /// <returns>The verified caller, as JSON.</returns>
    public static IResult WhoAmI(HttpContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        // Non-null because RequireAuth rejected a tokenless request before this handler.
        return Results.Ok(Identity(context.GetVerifiedUser()!));
    }

    /// <summary>
    /// Runs the agent as the verified caller.
    /// </summary>
    /// <param name="context">The verified request.</param>
    /// <param name="agent">The agent.</param>
    /// <param name="logger">Receives the identity line a reader watches for in the dev-run output.</param>
    /// <param name="cancellationToken">Cancels the run.</param>
    /// <returns>The caller and the conversation, or a 400 describing what was wrong with the body.</returns>
    public static async Task<IResult> AgentRun(
        HttpContext context,
        IdentityAgent agent,
        ILogger<IdentityEndpoints> logger,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(agent);
        ArgumentNullException.ThrowIfNull(logger);

        var user = context.GetVerifiedUser()!;
        logger.LogInformation(
            "[IDENTITY] verified caller subject={Subject} issuer={Issuer}",
            user.Subject,
            user.IssuerId);

        JsonDocument body;
        try
        {
            body = await JsonDocument.ParseAsync(
                context.Request.Body,
                cancellationToken: cancellationToken);
        }
        catch (JsonException)
        {
            return BadRequest("body must be JSON");
        }

        string? task;
        using (body)
        {
            // Read defensively rather than model-bound, so that a body which is valid JSON but the
            // wrong shape — an array, or a task that is a number — is a 400 with a message saying
            // so instead of a framework validation page.
            task = body.RootElement.ValueKind == JsonValueKind.Object
                && body.RootElement.TryGetProperty("task", out var value)
                && value.ValueKind == JsonValueKind.String
                    ? value.GetString()
                    : null;
        }

        if (string.IsNullOrWhiteSpace(task))
        {
            return BadRequest("task must be a non-empty string");
        }

        // Validated AFTER authentication, so a bad body from a verified caller is a 400 while the
        // same body from an anonymous one is still a 401.
        var messages = await agent.RunAsync(task, user.Subject, cancellationToken);

        return Results.Ok(new AgentRunResponse(Identity(user), messages));
    }

    /// <summary>
    /// The verified caller, as JSON.
    /// </summary>
    /// <remarks>
    /// Claim names only, never claim values: <c>user.Claims</c> is a real person's decoded
    /// credential, and echoing it back would leak whatever the identity provider chose to put
    /// there.
    /// </remarks>
    /// <param name="user">The verified caller.</param>
    /// <returns>The four fields this quickstart chooses to expose.</returns>
    private static IdentityResponse Identity(VerifiedUser user) => new(
        user.Subject,
        user.Tenant,
        user.IssuerId,
        // Already in ordinal order: VerifiedUser.Scopes is a sorted set, so the same token
        // serializes the same way on every host.
        [.. user.Scopes]);

    private static IResult BadRequest(string detail) =>
        Results.Json(new BadRequestResponse(BadRequestCode, detail), statusCode: 400);

    /// <summary>The <c>/whoami</c> body, and the <c>user</c> half of the agent reply.</summary>
    private sealed record IdentityResponse(
        [property: JsonPropertyName("subject")] string Subject,
        [property: JsonPropertyName("tenant")] string Tenant,
        [property: JsonPropertyName("issuer_id")] string IssuerId,
        [property: JsonPropertyName("scopes")] IReadOnlyList<string> Scopes);

    /// <summary>The <c>POST /agent/run</c> body.</summary>
    private sealed record AgentRunResponse(
        [property: JsonPropertyName("user")] IdentityResponse User,
        [property: JsonPropertyName("messages")] IReadOnlyList<string> Messages);

    /// <summary>This quickstart's own failure body. <c>error</c> is not an SDK error code.</summary>
    private sealed record BadRequestResponse(
        [property: JsonPropertyName("error")] string Error,
        [property: JsonPropertyName("detail")] string Detail);
}
