FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:10.0 AS build-env
WORKDIR /app

# Copy everything
COPY . ./
# Restore as distinct layers
RUN dotnet restore
# Build and publish a release
#
# `-c Release` is required: the throwaway offline issuer is compiled out of Release builds, so a
# container derived from this image cannot run with it.
RUN dotnet publish -c Release -o out

# Build runtime image
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
EXPOSE 8006
ENV ASPNETCORE_URLS=http://+:8006
COPY --from=build-env /app/out .
ENTRYPOINT ["dotnet", "agent.dll"]
