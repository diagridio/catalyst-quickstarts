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
/// The app under test: the quickstart's own handlers, agent, canned model and tool behind its own
/// middleware. Program.cs fixes its policy at start-up, so the two ASP.NET lines are rebuilt here
/// against <see cref="LocalIdentity.BuildLocalIssuer"/>, whose offline credentials are what make
/// the 200 and the 403 assertable with no Catalyst project. The outbound leg needs one.
/// </summary>
public sealed class IdentityAppFixture : IAsyncLifetime
{
    private WebApplication? _app;

    public LocalIdentity.LocalIssuer Issuer { get; private set; } = null!;

    public HttpClient Client { get; private set; } = null!;

    /// <inheritdoc />
    public async Task InitializeAsync()
    {
        // One throwaway issuer for the whole class: generating an RSA key is not free.
        Issuer = LocalIdentity.BuildLocalIssuer(LocalIdentity.RequiredScopes);

        var builder = WebApplication.CreateBuilder();
        // In-process, so there is no port to bind and no server to race.
        builder.WebHost.UseTestServer();
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
        // Lambdas, not the method groups Program.cs registers: the .NET 10 route analyzer cannot
        // handle a method group resolving into another assembly. The handlers are still the app's.
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

/// <summary>Tests for the inbound-identity behaviour this quickstart demonstrates.</summary>
public sealed class IdentityTests(IdentityAppFixture fixture) : IClassFixture<IdentityAppFixture>
{
    private const string TaskText = "What bookings do I have?";

    private const string TaskBody = $$"""{"task": "{{TaskText}}"}""";

    private const string VerifiedSubject = "alice@example.com";

    /// <summary>Enough callers to have several runs genuinely in flight together.</summary>
    private const int ConcurrentCallers = 32;

    // --- Fail closed, before any application code runs -------------------------

    /// <summary>A request with no credential is refused on every route.</summary>
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
        // An authorization verdict is not a cacheable response.
        Assert.Equal("no-store", response.Headers.CacheControl?.ToString());
    }

    /// <summary>An empty or blank header is treated as no credential at all.</summary>
    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public async Task AnEmptyHeaderIsTreatedAsNoCredential(string value)
    {
        using var response = await Send(HttpMethod.Get, "/whoami", value, body: null);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(OAuthErrorCodes.MissingToken, await ErrorCode(response));
    }

    /// <summary>Without the required scope a verified caller is 403: authn passed, authz failed.</summary>
    [Fact]
    public async Task ACredentialWithoutTheRequiredScopeIs403()
    {
        using var response = await Get("/whoami", fixture.Issuer.WrongScope);

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
        Assert.Equal(OAuthErrorCodes.MissingScope, await ErrorCode(response));
    }

    /// <summary>An expired credential is 401 — five minutes stale, to clear the verifier's skew.</summary>
    [Fact]
    public async Task AnExpiredCredentialIs401()
    {
        using var response = await Get("/whoami", fixture.Issuer.Expired);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(OAuthErrorCodes.Expired, await ErrorCode(response));
    }

    /// <summary>A token that is not a well-formed JWT is 401 <c>oauth.decode_error</c>.</summary>
    [Theory]
    [InlineData("Bearer not-a-jwt")]
    // A bare "Bearer" is not an empty credential: the prefix is "Bearer " and HTTP strips trailing
    // whitespace, so the bare word is read as malformed rather than as absent.
    [InlineData("Bearer")]
    public async Task AMalformedTokenIsA401(string header)
    {
        using var response = await Send(HttpMethod.Get, "/whoami", header, body: null);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Equal(OAuthErrorCodes.DecodeError, await ErrorCode(response));
    }

    // --- The verified caller reaches the app ------------------------------------

    /// <summary>
    /// A verified caller gets the documented identity. The field count is asserted because the
    /// projection must never start echoing a real person's decoded claims back.
    /// </summary>
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
    /// The thesis of the whole quickstart: the canned model asks for
    /// <see cref="CannedChatClient.ModelGuess"/>, and the answer names the verified caller instead.
    /// </summary>
    [Fact]
    public async Task TheToolAnswersForTheVerifiedCallerNotTheModelGuess()
    {
        using var response = await Post("/agent/run", TaskBody, fixture.Issuer.Verified);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        var raw = await response.Content.ReadAsStringAsync();
        using var document = JsonDocument.Parse(raw);
        var body = document.RootElement;
        Assert.Equal(VerifiedSubject, body.GetProperty("user").GetProperty("subject").GetString());

        // The exact three messages the README's offline section prints.
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

    /// <summary>The substitution lives in the tool the run is handed, not in the handler.</summary>
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
    /// Concurrent runs never serve one caller's bookings to another. One agent is shared by every
    /// request, and a merge that mutated the agent instead of the invocation would cross subjects
    /// silently — every response would still look well-formed — so each transcript is checked for
    /// its own caller and for no other.
    /// </summary>
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

    /// <summary>A run for nobody answers for nobody, rather than for the model's guess.</summary>
    [Fact]
    public async Task AnUnconfiguredSubjectDoesNotSilentlyBecomeTheModelGuess()
    {
        var transcript = await OfflineAgent().RunAsync(TaskText, string.Empty, CancellationToken.None);

        Assert.DoesNotContain(CannedChatClient.ModelGuess, string.Join(' ', transcript));
    }

    // --- Request validation -----------------------------------------------------

    /// <summary>A task that is not a non-empty string is a 400, checked after authentication.</summary>
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
    /// The issuer serves a JWKS the verifier can read. The encoding is pinned here: JWKS requires
    /// unpadded base64url, and a padded one surfaces elsewhere as an opaque 503.
    /// </summary>
    [Fact]
    public async Task TheIssuerServesAJwksTheVerifierCanRead()
    {
        using var http = new HttpClient();
        using var document = JsonDocument.Parse(
            await http.GetStringAsync(fixture.Issuer.Config.JwksUri!));

        var key = Assert.Single(document.RootElement.GetProperty("keys").EnumerateArray());
        Assert.Equal(LocalIdentity.KeyId, key.GetProperty("kid").GetString());
        Assert.Equal("RS256", key.GetProperty("alg").GetString());
        // AQAB is 65537, the standard RSA exponent, in unpadded base64url.
        Assert.Equal("AQAB", key.GetProperty("e").GetString());
        var modulus = key.GetProperty("n").GetString()!;
        Assert.DoesNotContain("=", modulus);
        Assert.DoesNotContain("+", modulus);
        Assert.DoesNotContain("/", modulus);
    }

    /// <summary>The app's agent on the offline path, for the tests that drive it without HTTP.</summary>
    private static IdentityAgent OfflineAgent() => IdentityAgent.Create(
        new CannedChatClient(offline: true),
        Tools.MyBookings,
        NullLoggerFactory.Instance);

    private Task<HttpResponseMessage> Get(string path, string token) =>
        Send(HttpMethod.Get, path, IdentityContext.BearerPrefix + token, body: null);

    private Task<HttpResponseMessage> Post(string path, string payload, string token) =>
        Send(HttpMethod.Post, path, IdentityContext.BearerPrefix + token, payload);

    /// <summary>
    /// One request, header value verbatim: <c>TryAddWithoutValidation</c> so the malformed values
    /// these tests care about reach the middleware instead of being rejected by the client first.
    /// </summary>
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
