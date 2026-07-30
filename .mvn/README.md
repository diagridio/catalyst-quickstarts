# `.mvn/maven.config`

Maven reads `maven.config` as raw command-line arguments, so it **cannot contain
comments** — every token becomes an argument and `#...` would fail the build.
That is why this explanation lives in a separate file.

## Why these flags exist

```
-Dmaven.wagon.rto=30000
-Dmaven.wagon.httpconnectionManager.ttlSeconds=60
-Dmaven.wagon.http.retryHandler.count=3
```

Maven has no useful default socket read timeout. When a Maven Central connection
dies mid-download, Maven neither reaps the socket nor retries — it blocks
indefinitely. Observed during a `workflow/java` e2e run: five sockets to
`repo.maven.apache.org` stuck in `CLOSE_WAIT`, four zero-byte `.tmp` files in
`~/.m2/repository`, and **15 minutes of wall-clock on 5 seconds of CPU** before
the harness's 900s `Run Process` timeout killed it (`rc=143`, SIGTERM). The other
three languages finished the same suite in 12–30s.

- `maven.wagon.rto=30000` — 30s socket read timeout, so a dead connection errors
  instead of hanging forever.
- `httpconnectionManager.ttlSeconds=60` — retires pooled connections after 60s so
  a half-dead keep-alive socket is not reused.
- `retryHandler.count=3` — retries the transfer once the timeout fires.

Raising the harness timeout does **not** fix this. A hang has no completion time,
so a higher ceiling only delays the identical failure.

## Scope

Maven discovers `.mvn` by walking up from the working directory (verified: with
this file present a flag applies from two directories below; from outside the repo
it does not). One file at the repo root therefore covers all three callers:

| caller | working directory |
| --- | --- |
| Robot harness `Build Quickstart` | `<api>/java` |
| CI "Pre-warm Maven dependencies" step | repo root |
| A reader following an `<api>/java/README.md` | `<api>/java` |

Because it applies to readers too, keep anything added here safe and
behaviour-neutral for a first-time quickstart user. These three only change
network timeout and retry behaviour; they do not alter what gets built.
