#if DEBUG
using System.Buffers.Text;
using System.Security.Cryptography;
using System.Text.Json;
using Diagrid.AI.Identity;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace EnterpriseIdentity;

/// <summary>
/// An offline stand-in for the Catalyst identity plane, enabled with
/// <c>DIAGRID_QUICKSTART_IDENTITY=local</c>. Debug-only, and never a real deployment: the throwaway
/// private key lives in this process's memory and the credentials it signs are logged in plain text.
/// </summary>
public static class LocalIdentity
{
    /// <summary>The <c>iss</c> the offline credentials carry.</summary>
    public const string Issuer = "https://local-identity.invalid";

    public const string Audience = "catalyst-quickstart";

    public const string KeyId = "local-quickstart-key";

    /// <summary>
    /// The scope the offline issuer demands. On the Catalyst path, require the scopes your own
    /// identity provider issues.
    /// </summary>
    public static readonly string[] RequiredScopes = ["agent.invoke"];

    private const int DefaultLifetimeSeconds = 3600;

    /// <summary>How stale the expired credential is: past the verifier's 120s skew allowance.</summary>
    private const int ExpiredLifetimeSeconds = -300;

    /// <summary>A running throwaway issuer: its policy, and the credentials it accepts.</summary>
    /// <param name="Verified">Carries the required scopes — 200.</param>
    /// <param name="WrongScope">Verifies, carries the wrong scope — 403 <c>oauth.missing_scope</c>.</param>
    /// <param name="Expired">Carries the required scopes but is stale — 401 <c>oauth.expired</c>.</param>
    public sealed record LocalIssuer(
        OAuthConfig Config,
        string Verified,
        string WrongScope,
        string Expired);

    public static LocalIssuer BuildLocalIssuer(IReadOnlyCollection<string> requiredScopes)
    {
        ArgumentNullException.ThrowIfNull(requiredScopes);

        // Not disposed: it backs the JWKS the verifier fetches for as long as the app runs.
        var key = RSA.Create(2048);
        var jwksUri = StartJwksEndpoint(JwksDocument(key));
        var now = DateTime.UtcNow;

        return new LocalIssuer(
            Config: new OAuthConfig
            {
                Scopes = [.. requiredScopes],
                // With both set, the verifier skips discovery entirely and never looks for a sidecar.
                Issuer = Issuer,
                Audience = Audience,
                JwksUri = jwksUri,
            },
            Verified: Mint(key, now, "alice@example.com", requiredScopes),
            WrongScope: Mint(key, now, "bob@example.com", ["reports.read"]),
            Expired: Mint(key, now, "carol@example.com", requiredScopes, ExpiredLifetimeSeconds));
    }

    /// <summary>Logs the issuer's credentials, in plain text, so a reader can paste them.</summary>
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

    /// <summary>The key's public half, with its numbers in the unpadded base64url JWKS requires.</summary>
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
    /// Serves <paramref name="jwks"/> on a loopback port the OS picks. Never disposed: it has to
    /// answer the verifier's fetch for as long as the process lives.
    /// </summary>
    private static string StartJwksEndpoint(string jwks)
    {
        var builder = WebApplication.CreateSlimBuilder();
        builder.WebHost.UseUrls("http://127.0.0.1:0");
        // Otherwise this host's request log buries the credentials a reader is here to copy.
        builder.Logging.ClearProviders();

        var app = builder.Build();
        app.MapGet("/jwks.json", () => Results.Text(jwks, "application/json"));
        app.Start();

        // Read after Start: the bound port is only known once Kestrel has taken it.
        var origin = app.Urls.First();
        return $"{origin}/jwks.json";
    }

    /// <summary>
    /// Signs one credential. A negative <paramref name="lifetimeSeconds"/> backdates the whole
    /// window, producing one that already expired.
    /// </summary>
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
