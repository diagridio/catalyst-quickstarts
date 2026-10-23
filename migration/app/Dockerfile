ARG BASE_IMAGE=golang:1.24
ARG RUNTIME_IMAGE=alpine:3.22

FROM --platform=$BUILDPLATFORM ${BASE_IMAGE} AS build-env
ARG TARGETOS
ARG TARGETARCH
WORKDIR /app

# Dependencies as their own layer, so a source edit does not re-download them.
COPY go.mod go.sum ./
RUN go mod download

COPY *.go ./
# CGO_ENABLED=0 for a static binary the runtime image needs no libc for.
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o out/app .

FROM ${RUNTIME_IMAGE}
RUN adduser -D -u 10001 app
COPY --from=build-env /app/out/app /usr/local/bin/app
USER 10001
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/app"]
