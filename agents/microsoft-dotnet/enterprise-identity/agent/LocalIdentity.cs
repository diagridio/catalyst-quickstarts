#if DEBUG
using System.Buffers.Text;
using System.Security.Cryptography;
using System.Text.Json;
using Diagrid.AI.Identity;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace EnterpriseIdentity;

/// <summary>
/// An offline stand-in for the Catalyst identity plane.
/// </summary>
/// <remarks>
/// <para>
/// Opt in with <c>DIAGRID_QUICKSTART_IDENTITY=local</c>. It generates a throwaway RSA key, serves
/// the public half as JWKS on a loopback port, and logs three ready-to-paste credentials so every
/// response this quickstart describes — 200, 403 and 401 — is reachable with no Catalyst project
/// and no identity provider.
/// </para>
/// <para>
/// Why it exists: 403 <c>oauth.missing_scope</c> needs a credential that genuinely verifies.
/// Against real Catalyst you cannot mint one that lacks a scope, and with no issuer configured at
/// all the middleware answers 503 <c>oauth.not_configured</c> instead. This is the only way the
/// scope check is observable. It is the same trade <see cref="CannedChatClient"/> makes for the
/// model: free, offline, identical on every run.
/// </para>
/// <para>
/// WHY THE WHOLE FILE IS BEHIND <c>#if DEBUG</c>. The python sibling keeps its issuer out of the
/// container by listing the file in <c>.dockerignore</c>, so the import fails and the app refuses
/// to start. A C# source file cannot be dropped from a compiled assembly that way, so the guard
/// moved to compile time: the Dockerfile publishes <c>-c Release</c>, this type does not exist in
/// that build, and Program.cs's Release branch throws at start-up when the variable is set.
/// Setting it on a container therefore fails closed instead of quietly trusting tokens the app
/// minted itself.
/// </para>
/// <para>
/// Never a real deployment. The private key lives in this process's memory and the credentials it
/// signs are logged in plain text.
/// </para>
/// </remarks>
public static class LocalIdentity
{
    /// <summary>The <c>iss</c> the offline credentials carry, and the value the verifier expects.</summary>
    public const string Issuer = "https://local-identity.invalid";

    /// <summary>The <c>aud</c> the offline credentials carry.</summary>
    public const string Audience = "catalyst-quickstart";

    /// <summary>The key id in both the JWKS document and every token header.</summary>
    public const string KeyId = "local-quickstart-key";

    /// <summary>
    /// The scope the offline issuer demands.
    /// </summary>
    /// <remarks>
    /// Only the offline issuer demands one. Scopes come from your identity provider, and a Diagrid
    /// login carries <c>openid profile email offline_access</c> and nothing else, so requiring one
    /// on the Catalyst path would answer 403 for everybody. See "On scopes" in the README.
    /// </remarks>
    public static readonly string[] RequiredScopes = ["agent.invoke"];

    /// <summary>How long a freshly minted credential is good for.</summary>
    private const int DefaultLifetimeSeconds = 3600;

    /// <summary>
    /// How stale the expired credential is.
    /// </summary>
    /// <remarks>
    /// Diagrid.AI.Identity's verifier allows <see cref="JwksVerifier.ClockSkewSeconds"/> (120s) of
    /// clock skew, so a credential that expired a minute ago still verifies. Anything demonstrating
    /// <c>oauth.expired</c> has to be older than that.
    /// </remarks>
    private const int ExpiredLifetimeSeconds = -300;

    /// <summary>
    /// A running throwaway issuer: the policy it implies, and the credentials it accepts.
    /// </summary>
    /// <remarks>
    /// Program.cs needs only <see cref="Config"/>. The three credentials are returned as well so
    /// that the unit tests can present them, which is the only way the 200 and 403 paths are
    /// assertable without a Catalyst project.
    /// </remarks>
    /// <param name="Config">The identity policy, pointed at this issuer.</param>
    /// <param name="Verified">Carries the required scopes — 200.</param>
    /// <param name="WrongScope">Verifies, carries the wrong scope — 403 <c>oauth.missing_scope</c>.</param>
    /// <param name="Expired">Carries the required scopes but is stale — 401 <c>oauth.expired</c>.</param>
    public sealed record LocalIssuer(
        OAuthConfig Config,
        string Verified,
        string WrongScope,
        string Expired);

    /// <summary>
    /// Starts the throwaway issuer and mints the three credentials it accepts.
    /// </summary>
    /// <remarks>
    /// Logs nothing: <see cref="LogCredentials"/> is what prints the credentials for a reader to
    /// paste, and a test that already holds them has no reason to write three JWTs to its own
    /// output.
    /// </remarks>
    /// <param name="requiredScopes">The scopes the verified credential must carry.</param>
    /// <returns>The running issuer.</returns>
    public static LocalIssuer BuildLocalIssuer(IReadOnlyCollection<string> requiredScopes)
    {
        ArgumentNullException.ThrowIfNull(requiredScopes);

        // Not disposed, and not owned by a `using`: the key has to outlive this method because it
        // signs tokens below and backs the JWKS the verifier fetches for as long as the app runs.
        var key = RSA.Create(2048);
        var jwksUri = StartJwksEndpoint(JwksDocument(key));
        var now = DateTime.UtcNow;

        return new LocalIssuer(
            Config: new OAuthConfig
            {
                Scopes = [.. requiredScopes],
                // Set explicitly, which is what makes this offline: with both Issuer and JwksUri
                // present the verifier skips discovery entirely and never looks for a sidecar.
                Issuer = Issuer,
                Audience = Audience,
                JwksUri = jwksUri,
                // AllowInsecureJwks stays off. A loopback http:// endpoint is exempt from the
                // https requirement on its own, so nothing here opts into plaintext generally.
            },
            Verified: Mint(key, now, "alice@example.com", requiredScopes),
            WrongScope: Mint(key, now, "bob@example.com", ["reports.read"]),
            Expired: Mint(key, now, "carol@example.com", requiredScopes, ExpiredLifetimeSeconds));
    }

    /// <summary>
    /// Logs the issuer's credentials so a reader can paste them.
    /// </summary>
    /// <remarks>
    /// These lines are the ones the README's "## Run Offline Without a Catalyst Project" block
    /// reproduces, so their text is part of the documented output.
    /// </remarks>
    /// <param name="logger">Receives the credentials, in plain text.</param>
    /// <param name="issuer">The running issuer.</param>
    public static void LogCredentials(ILogger logger, LocalIssuer issuer)
    {
        ArgumentNullException.ThrowIfNull(logger);
        ArgumentNullException.ThrowIfNull(issuer);

        logger.LogWarning("LOCAL IDENTITY MODE - throwaway keys, never a real deployment");
        logger.LogInformation("JWKS served at {JwksUri}", issuer.Config.JwksUri);
        logger.LogInformation("200 (verified, has {Scopes}):", string.Join(' ', issuer.Config.Scopes));
        logger.LogInformation("  {Token}", issuer.Verified);
        logger.LogInformation("403 (verifies, wrong scope) oauth.missing_scope:");
        logger.LogInformation("  {Token}", issuer.WrongScope);
        logger.LogInformation("401 (expired 5 minutes ago) oauth.expired:");
        logger.LogInformation("  {Token}", issuer.Expired);
    }

    /// <summary>
    /// The JWKS document for <paramref name="key"/>'s public half.
    /// </summary>
    /// <remarks>
    /// The numbers are unpadded base64url, which is what JWKS requires:
    /// <see cref="Base64Url"/> emits that spelling, where a
    /// <see cref="Convert.ToBase64String(byte[])"/> would emit <c>+</c>, <c>/</c> and <c>=</c> and
    /// the verifier would reject the key — surfacing as an opaque 503 rather than as a
    /// wrong-encoding error.
    /// </remarks>
    /// <param name="key">The signing key.</param>
    /// <returns>The JWKS document, as JSON.</returns>
    private static string JwksDocument(RSA key)
    {
        ArgumentNullException.ThrowIfNull(key);

        var parameters = key.ExportParameters(includePrivateParameters: false);

        return JsonSerializer.Serialize(new
        {
            keys = new[]
            {
                new
                {
                    kty = "RSA",
                    kid = KeyId,
                    use = "sig",
                    alg = "RS256",
                    n = Base64Url.EncodeToString(parameters.Modulus!),
                    e = Base64Url.EncodeToString(parameters.Exponent!),
                },
            },
        });
    }

    /// <summary>
    /// Serves <paramref name="jwks"/> on a loopback port the OS picks.
    /// </summary>
    /// <remarks>
    /// Port 0, so this never collides with the app. The host is started and deliberately never
    /// disposed: it has to answer the verifier's fetch for as long as the process lives, and the
    /// process ending is what shuts it down.
    /// </remarks>
    /// <param name="jwks">The JWKS document to serve.</param>
    /// <returns>The absolute JWKS URI.</returns>
    private static string StartJwksEndpoint(string jwks)
    {
        var builder = WebApplication.CreateSlimBuilder();
        builder.WebHost.UseUrls("http://127.0.0.1:0");
        // Otherwise this second host's own request log buries the app's startup lines, including
        // the three credentials a reader is here to copy.
        builder.Logging.ClearProviders();

        var app = builder.Build();
        app.MapGet("/jwks.json", () => Results.Text(jwks, "application/json"));
        app.Start();

        // Read after Start, not before: the bound port is only known once Kestrel has taken it.
        var origin = app.Urls.First();
        return $"{origin}/jwks.json";
    }

    /// <summary>
    /// Signs one credential.
    /// </summary>
    /// <param name="key">The signing key.</param>
    /// <param name="now">The reference time, shared by every credential in one issuer.</param>
    /// <param name="subject">The <c>sub</c> claim.</param>
    /// <param name="scopes">The <c>scp</c> claim, space-delimited on the wire.</param>
    /// <param name="lifetimeSeconds">
    /// How long the credential is good for. A NEGATIVE value is a credential that already expired
    /// that many seconds ago; the issue time is backdated with it so the window stays coherent,
    /// which <see cref="SecurityTokenDescriptor"/> requires and which is also what a genuinely
    /// stale credential looks like.
    /// </param>
    /// <returns>The signed compact JWT.</returns>
    private static string Mint(
        RSA key,
        DateTime now,
        string subject,
        IEnumerable<string> scopes,
        int lifetimeSeconds = DefaultLifetimeSeconds)
    {
        var expires = now.AddSeconds(lifetimeSeconds);
        var issuedAt = expires.AddSeconds(-DefaultLifetimeSeconds);

        return new JsonWebTokenHandler().CreateToken(new SecurityTokenDescriptor
        {
            Issuer = Issuer,
            Audience = Audience,
            IssuedAt = issuedAt,
            NotBefore = issuedAt,
            Expires = expires,
            Claims = new Dictionary<string, object>
            {
                ["sub"] = subject,
                ["tid"] = "local-tenant",
                ["scp"] = string.Join(' ', scopes.Order(StringComparer.Ordinal)),
            },
            SigningCredentials = new SigningCredentials(
                new RsaSecurityKey(key) { KeyId = KeyId },
                SecurityAlgorithms.RsaSha256),
        });
    }
}
#endif
