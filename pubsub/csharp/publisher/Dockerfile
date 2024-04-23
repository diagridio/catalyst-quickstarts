# Learn about building .NET container images:
# https://github.com/dotnet/dotnet-docker/blob/main/samples/README.md
FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:8.0 AS build
ARG TARGETARCH
WORKDIR /source

# Copy everything
COPY /*.csproj .
RUN dotnet restore -a $TARGETARCH


# Build and publish a release
COPY . .
RUN dotnet publish -a $TARGETARCH --no-restore -o /app

# Build runtime image
FROM mcr.microsoft.com/dotnet/aspnet:8.0
EXPOSE 5001
ENV ASPNETCORE_URLS=http://+:5001
WORKDIR /app
COPY --from=build /app .
ENTRYPOINT ["dotnet", "publisher.dll"]