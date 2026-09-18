using System.Net;
using System.Text;
using System.Text.Json;
using Diagrid.AI.Identity;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace EnterpriseIdentity.Tests;

/// <summary>
/// The app under test: the quickstart's own handlers behind the quickstart's own middleware.
/// </summary>
/// <remarks>
/// <para>
/// Why the app is re-assembled instead of started: Program.cs reads its environment and installs its
/// middleware at start-up, which is the two-line shape the README teaches, so by the time it is
/// running its policy is fixed and cannot be pointed at this fixture's issuer. The two ASP.NET lines
/// are therefore rebuilt here — but the handlers, the agent, the canned model, the tool and the
/// required scope are all the app's own objects, so drift in any of them fails these tests rather
/// than sliding past.
/// </para>
/// <para>
/// No Catalyst, no Dapr, no network and no API key.
/// <see cref="LocalIdentity.BuildLocalIssuer"/> stands in for the Catalyst identity plane: it signs
/// with a throwaway key it generates in-process and serves the public half as JWKS on a loopback
/// port, so a credential that genuinely verifies is available offline. That is what makes the 200
/// and the 403 assertable here at all — the Robot suite next door can present no credential and
/// therefore asserts only the two 401s.
/// </para>
/// <para>
/// What is deliberately not tested: the outbound leg. Carrying the caller onward to an MCP tool
/// needs a Catalyst project, so it is exercised by the README walkthrough rather than here. This
/// fixture pins the app to offline mode, where the agent calls the in-process tool and no request
/// leaves the machine.
/// </para>
/// </remarks>
public sealed class IdentityAppFixture : IAsyncLifetime
{
    private WebApplication? _app;

    /// <summary>Gets the throwaway issuer whose credentials the tests present.</summary>
    public LocalIdentity.LocalIssuer Issuer { get; private set; } = null!;

    /// <summary>Gets the in-process client that drives the app.</summary>
    public HttpClient Client { get; private set; } = null!;

    /// <inheritdoc />
    public async Task InitializeAsync()
    {
        // One throwaway issuer for the whole class: generating an RSA key is not free.
        Issuer = LocalIdentity.BuildLocalIssuer(LocalIdentity.RequiredScopes);

        var builder = WebApplication.CreateBuilder();
        // In-process, so there is no port to bind and no server to race.
        builder.WebHost.UseTestServer();
        // The app's own logging is not under test, and a test run has nowhere useful to put it.
        builder.Logging.ClearProviders();

        builder.Services.AddDiagridIdentity(config =>
        {
            config.Scopes = Issuer.Config.Scopes;
            config.Issuer = Issuer.Config.Issuer;
            config.Audience = Issuer.Config.Audience;
            config.JwksUri = Issuer.Config.JwksUri;
        });

        builder.Services.AddSingleton(serviceProvider => IdentityAgent.Create(
            new CannedChatClient(offline: true),
            Tools.MyBookings,
            serviceProvider.GetRequiredService<ILoggerFactory>()));

        var app = builder.Build();
        app.UseDiagridIdentity();
        // Lambdas rather than the method groups Program.cs registers, and not by preference: the
        // .NET 10 RouteHandlerAnalyzer throws IndexOutOfRangeException on a method group that
        // resolves into another assembly, which surfaces as an AD0001 warning on every build. The
        // handlers invoked are still the app's own.
        app.MapGet("/whoami", (HttpContext context) => IdentityEndpoints.WhoAmI(context));
        app.MapPost("/agent/run", (HttpContext context, IdentityAgent agent, ILogger<IdentityEndpoints> logger, CancellationToken ct) => IdentityEndpoints.AgentRun(context, agent, logger, ct));

        await app.StartAsync();
        _app = app;
        Client = app.GetTestClient();
    }

    /// <inheritdoc />
    public async Task DisposeAsync()
    {
        Client?.Dispose();
        if (_app is not null)
        {
            await _app.DisposeAsync();
        }
    }
}

/// <summary>
/// Tests for the inbound-identity behaviour this quickstart demonstrates.
/// </summary>
/// <remarks>
/// Run from the quickstart directory with <c>dotnet test unit-tests</c>.
/// </remarks>
/// <param name="fixture">The re-assembled app and its offline issuer.</param>
public sealed class IdentityTests(IdentityAppFixture fixture) : IClassFixture<IdentityAppFixture>
{
    /// <summary>The task both documented requests send.</summary>
    private const string TaskText = "What bookings do I have?";

    private const string TaskBody = $$"""{"task": "{{TaskText}}"}""";

    private const string VerifiedSubject = "alice@example.com";

    /// <summary>
    /// How many callers <see cref="ConcurrentRunsDoNotCrossSubjects"/> runs at once.
    /// </summary>
    /// <remarks>
    /// Enough to have several runs genuinely in flight together on any CI machine, and small
    /// enough that the quadratic cross-check below stays instant.
    /// </remarks>
    private const int ConcurrentCallers = 32;

    // --- Fail closed, before any application code runs -------------------------

    /// <summary>
    /// A request with no credential is refused on every route.
    /// </summary>
    /// <remarks>
    /// <c>RequireAuth</c> defaults to <see langword="true"/> and <c>OAuthMiddleware</c> wraps every
    /// route, so this is the app-wide rule the README claims, checked on both documented routes
    /// rather than on one and assumed for the other. The exact body is the one the Robot suite
    /// asserts against a live Catalyst project.
    /// </remarks>
    /// <param name="method">The HTTP method.</param>
    /// <param name="path">The documented route.</param>
    [Theory]
    [InlineData("GET", "/whoami")]
    [InlineData("POST", "/agent/run")]
    public async Task NoCredentialIsRefusedOnEveryRoute(string method, string path)
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), path)
        {
            Content = new StringContent(TaskBody, Encoding.UTF8, "application/json"),
        };

        using var response = await fixture.Client.SendAsync(request);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(OAuthErrorCodes.MissingToken, await ErrorCode(response));
        // An authorization verdict is not a cacheable response. This header is the middleware's, not
        // ASP.NET's, and the README documents it.
        Assert.Equal("no-store", response.Headers.CacheControl?.ToString());
    }

    /// <summary>
    /// An empty or blank header is treated as no credential at all.
    /// </summary>
    /// <remarks>
    /// The README claims "no header, or an empty one" is 401, so both halves are checked. The
    /// middleware trims the value, so a blank one leaves an empty token and takes the same branch as
    /// an absent header.
    /// </remarks>
    /// <param name="value">The header value to send.</param>
    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public async Task AnEmptyHeaderIsTreatedAsNoCredential(string value)
    {
        using var response = await Send(HttpMethod.Get, "/whoami", value, body: null);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(OAuthErrorCodes.MissingToken, await ErrorCode(response));
    }

    /// <summary>
    /// A verified caller without the required scope is refused 403, not 401.
    /// </summary>
    /// <remarks>
    /// The distinction is the point: authentication succeeded and authorization failed. The
    /// credential is signed by the same issuer and has not expired — it simply carries
    /// <c>reports.read</c>.
    /// </remarks>
    [Fact]
    public async Task ACredentialWithoutTheRequiredScopeIs403()
    {
        using var response = await Get("/whoami", fixture.Issuer.WrongScope);

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
        Assert.Equal(OAuthErrorCodes.MissingScope, await ErrorCode(response));
    }

    /// <summary>
    /// An expired credential is refused 401 <c>oauth.expired</c>.
    /// </summary>
    /// <remarks>
    /// Five minutes stale, because the verifier allows
    /// <see cref="JwksVerifier.ClockSkewSeconds"/> of clock skew. If LocalIdentity's expired
    /// lifetime ever creeps inside that window this returns 200 and fails here rather than in a
    /// reader's terminal.
    /// </remarks>
    [Fact]
    public async Task AnExpiredCredentialIs401()
    {
        using var response = await Get("/whoami", fixture.Issuer.Expired);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(OAuthErrorCodes.Expired, await ErrorCode(response));
    }

    /// <summary>
    /// A token that is not a well-formed JWT is 401 <c>oauth.decode_error</c>.
    /// </summary>
    /// <remarks>
    /// Asserting the code and not just the status: 401 alone would still pass if a future version
    /// routed this through <c>oauth.missing_token</c> or <c>oauth.invalid_signature</c>, and those
    /// mean different things to a reader debugging a real credential.
    /// </remarks>
    /// <param name="header">The header value to send.</param>
    [Theory]
    [InlineData("Bearer not-a-jwt")]
    // A bare "Bearer" with nothing after it, which looks like an empty credential but is not one.
    // The prefix is "Bearer " — the trailing space is part of it — and HTTP strips trailing header
    // whitespace, so the prefix never matches and the literal string "Bearer" is taken as the token.
    // It therefore lands here, among the malformed tokens, rather than on the missing-token path an
    // empty header gets. Same status either way, but a different code, and that is worth pinning.
    [InlineData("Bearer")]
    public async Task AMalformedTokenIsA401(string header)
    {
        using var response = await Send(HttpMethod.Get, "/whoami", header, body: null);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(OAuthErrorCodes.DecodeError, await ErrorCode(response));
    }

    // --- The verified caller reaches the app ------------------------------------

    /// <summary>
    /// A verified caller gets exactly the identity the README documents.
    /// </summary>
    /// <remarks>
    /// Claim NAMES only, and the field count is asserted for that reason:
    /// <c>VerifiedUser.Claims</c> is a real person's decoded credential in a deployment, and the
    /// identity projection must not start echoing it back.
    /// </remarks>
    [Fact]
    public async Task AVerifiedCallerGetsTheDocumentedIdentity()
    {
        using var response = await Get("/whoami", fixture.Issuer.Verified);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var body = await Body(response);
        Assert.Equal(VerifiedSubject, body.GetProperty("subject").GetString());
        Assert.Equal("local-tenant", body.GetProperty("tenant").GetString());
        Assert.Equal(LocalIdentity.Issuer, body.GetProperty("issuer_id").GetString());
        Assert.Equal(
            LocalIdentity.RequiredScopes,
            body.GetProperty("scopes").EnumerateArray().Select(scope => scope.GetString()!).ToArray());
        Assert.Equal(4, body.EnumerateObject().Count());
        Assert.False(body.TryGetProperty("claims", out _));
    }

    /// <summary>
    /// The thesis of the whole quickstart, asserted end to end.
    /// </summary>
    /// <remarks>
    /// The canned model asks <c>my_bookings</c> for <see cref="CannedChatClient.ModelGuess"/>. The
    /// tool the run was handed is closed over the subject the middleware verified, so the answer
    /// names <c>alice@example.com</c> and the model's guess appears nowhere in the response.
    /// </remarks>
    [Fact]
    public async Task TheToolAnswersForTheVerifiedCallerNotTheModelGuess()
    {
        using var response = await Post("/agent/run", TaskBody, fixture.Issuer.Verified);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var raw = await response.Content.ReadAsStringAsync();
        using var document = JsonDocument.Parse(raw);
        var body = document.RootElement;
        Assert.Equal(VerifiedSubject, body.GetProperty("user").GetProperty("subject").GetString());

        // The exact three messages the README's offline section prints: the task, the tool's answer,
        // and the model's summary of it.
        Assert.Equal(
            [
                TaskText,
                $"Bookings for {VerifiedSubject}: Grand Ballroom on March 15th, 9AM-1PM; "
                    + "Rooftop Terrace on March 22nd, 6PM-11PM.",
                "You have two bookings: the Grand Ballroom on March 15th (9AM-1PM) and "
                    + "the Rooftop Terrace on March 22nd (6PM-11PM).",
            ],
            body.GetProperty("messages").EnumerateArray().Select(message => message.GetString()!).ToArray());
        Assert.DoesNotContain(CannedChatClient.ModelGuess, raw);
    }

    /// <summary>
    /// The substitution lives in the tool the run is handed, not in the request handler.
    /// </summary>
    /// <remarks>
    /// Invokes the app's own agent directly, with no HTTP and no middleware, which is exactly why
    /// the verified subject travels as per-run configuration rather than as a message the model
    /// could rewrite.
    /// </remarks>
    [Fact]
    public async Task SubstitutionHappensInTheToolNotInTheHandler()
    {
        var transcript = await OfflineAgent().RunAsync(TaskText, "dave@example.com", CancellationToken.None);

        var toolAnswer = Assert.Single(
            transcript,
            message => message.StartsWith("Bookings for", StringComparison.Ordinal));
        Assert.Contains("dave@example.com", toolAnswer);
        Assert.DoesNotContain(CannedChatClient.ModelGuess, toolAnswer);
    }

    /// <summary>
    /// Concurrent runs never serve one caller's bookings to another.
    /// </summary>
    /// <remarks>
    /// <para>
    /// One singleton <see cref="IdentityAgent"/> — wrapping one <c>ChatClientAgent</c> — is shared
    /// by every request, and the caller's tool arrives as per-run <c>ChatClientAgentRunOptions</c>
    /// that the framework merges with the agent's own defaults.
    /// </para>
    /// <para>
    /// A merge that mutated the agent instead of the invocation would cross two callers' subjects
    /// under load, and the failure mode is a data leak rather than an exception: every response
    /// would still look well-formed. So this asserts both halves — each transcript names its own
    /// caller, AND no other caller's subject appears in it.
    /// </para>
    /// </remarks>
    [Fact]
    public async Task ConcurrentRunsDoNotCrossSubjects()
    {
        var agent = OfflineAgent();
        var subjects = Enumerable.Range(0, ConcurrentCallers)
            .Select(index => $"user{index}@example.com")
            .ToArray();

        var transcripts = await Task.WhenAll(
            subjects.Select(subject => agent.RunAsync(TaskText, subject, CancellationToken.None)));

        for (var index = 0; index < subjects.Length; index++)
        {
            var toolAnswer = Assert.Single(
                transcripts[index],
                message => message.StartsWith("Bookings for", StringComparison.Ordinal));
            Assert.Contains(subjects[index], toolAnswer);
            Assert.DoesNotContain(CannedChatClient.ModelGuess, toolAnswer);
            foreach (var other in subjects.Where(candidate => candidate != subjects[index]))
            {
                Assert.DoesNotContain(other, toolAnswer);
            }
        }
    }

    /// <summary>
    /// An unconfigured subject must not silently become the model's guess.
    /// </summary>
    /// <remarks>
    /// An agent run for nobody answers for nobody. That is the safe direction; falling through to
    /// the model's <c>someone@example.com</c> would be the unsafe one.
    /// </remarks>
    [Fact]
    public async Task AnUnconfiguredSubjectDoesNotSilentlyBecomeTheModelGuess()
    {
        var transcript = await OfflineAgent().RunAsync(TaskText, string.Empty, CancellationToken.None);

        Assert.DoesNotContain(CannedChatClient.ModelGuess, string.Join(' ', transcript));
    }

    // --- Request validation -----------------------------------------------------

    /// <summary>
    /// A task that is not a non-empty string is a 400.
    /// </summary>
    /// <remarks>
    /// Validated after authentication, so a bad body from a verified caller is a 400 while the same
    /// body from an anonymous one is still a 401.
    /// </remarks>
    /// <param name="payload">The raw request body.</param>
    [Theory]
    [InlineData("{}")]
    [InlineData("""{"task": ""}""")]
    [InlineData("""{"task": "   "}""")]
    [InlineData("""{"task": 7}""")]
    [InlineData("[]")]
    public async Task ATaskThatIsNotANonEmptyStringIs400(string payload)
    {
        using var response = await Post("/agent/run", payload, fixture.Issuer.Verified);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("bad_request", await ErrorCode(response));
    }

    /// <summary>A body that is not JSON at all is a 400 naming that.</summary>
    [Fact]
    public async Task ABodyThatIsNotJsonIs400()
    {
        using var response = await Post("/agent/run", "not json", fixture.Issuer.Verified);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("body must be JSON", (await Body(response)).GetProperty("detail").GetString());
    }

    // --- The offline issuer itself ----------------------------------------------

    /// <summary>
    /// The issuer serves a JWKS document the verifier can read.
    /// </summary>
    /// <remarks>
    /// The middleware fetches this over the loopback port the OS picked. If it were malformed every
    /// credential-bearing test above would fail as a 503, so this makes the cause legible. The
    /// encoding is pinned here too: JWKS requires unpadded base64url, and a
    /// <c>Convert.ToBase64String</c> would emit <c>+</c>, <c>/</c> and <c>=</c> and be rejected as
    /// an opaque 503 rather than as a wrong-encoding error.
    /// </remarks>
    [Fact]
    public async Task TheIssuerServesAJwksTheVerifierCanRead()
    {
        using var http = new HttpClient();
        using var document = JsonDocument.Parse(
            await http.GetStringAsync(fixture.Issuer.Config.JwksUri!));

        var key = Assert.Single(document.RootElement.GetProperty("keys").EnumerateArray());
        Assert.Equal(LocalIdentity.KeyId, key.GetProperty("kid").GetString());
        Assert.Equal("RS256", key.GetProperty("alg").GetString());
        // AQAB is the standard RSA exponent, 65537, in unpadded base64url. Getting that spelling
        // wrong is the failure this pins.
        Assert.Equal("AQAB", key.GetProperty("e").GetString());
        var modulus = key.GetProperty("n").GetString()!;
        Assert.DoesNotContain("=", modulus);
        Assert.DoesNotContain("+", modulus);
        Assert.DoesNotContain("/", modulus);
    }

    /// <summary>
    /// The app's agent on the offline path, for the two tests that drive it without HTTP.
    /// </summary>
    /// <returns>The agent.</returns>
    private static IdentityAgent OfflineAgent() => IdentityAgent.Create(
        new CannedChatClient(offline: true),
        Tools.MyBookings,
        NullLoggerFactory.Instance);

    private Task<HttpResponseMessage> Get(string path, string token) =>
        Send(HttpMethod.Get, path, IdentityContext.BearerPrefix + token, body: null);

    private Task<HttpResponseMessage> Post(string path, string payload, string token) =>
        Send(HttpMethod.Post, path, IdentityContext.BearerPrefix + token, payload);

    /// <summary>
    /// One request, with the header value sent verbatim.
    /// </summary>
    /// <remarks>
    /// <c>TryAddWithoutValidation</c> so that the malformed values the tests care about — an empty
    /// header, a bare <c>Bearer</c> — reach the middleware rather than being rejected by
    /// <see cref="HttpClient"/> first.
    /// </remarks>
    /// <param name="method">The HTTP method.</param>
    /// <param name="path">The route.</param>
    /// <param name="userToken">The <c>X-Diagrid-User-Token</c> value, exactly as it should arrive.</param>
    /// <param name="body">The request body, or <see langword="null"/> for none.</param>
    /// <returns>The response.</returns>
    private Task<HttpResponseMessage> Send(HttpMethod method, string path, string userToken, string? body)
    {
        var request = new HttpRequestMessage(method, path);
        request.Headers.TryAddWithoutValidation(IdentityContext.UserTokenHeader, userToken);
        if (body is not null)
        {
            request.Content = new StringContent(body, Encoding.UTF8, "application/json");
        }

        return fixture.Client.SendAsync(request);
    }

    private static async Task<JsonElement> Body(HttpResponseMessage response)
    {
        using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        return document.RootElement.Clone();
    }

    private static async Task<string?> ErrorCode(HttpResponseMessage response) =>
        (await Body(response)).GetProperty("error").GetString();
}
