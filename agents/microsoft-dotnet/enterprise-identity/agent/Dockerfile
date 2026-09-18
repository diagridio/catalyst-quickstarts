FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:10.0 AS build-env
WORKDIR /app

# Copy everything
COPY . ./
# Restore as distinct layers
RUN dotnet restore
# Build and publish a release
#
# `-c Release` is load-bearing here, not habit. It carries the intent the python sibling puts in its
# .dockerignore: a compiled language cannot omit a source file from the image, so the throwaway
# offline issuer is behind `#if DEBUG` and Program.cs's Release branch throws at start-up when
# DIAGRID_QUICKSTART_IDENTITY=local is set. Setting that variable on a container derived from this
# quickstart therefore refuses to start rather than quietly trusting tokens the app minted itself.
RUN dotnet publish -c Release -o out

# Build runtime image
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
EXPOSE 8006
ENV ASPNETCORE_URLS=http://+:8006
COPY --from=build-env /app/out .
ENTRYPOINT ["dotnet", "agent.dll"]
