# The builder's Go must be at least the 1.26.4 go.mod asks for, which is what
# github.com/diagridio/go-ai v0.2.0 requires.
ARG BASE_IMAGE=golang:1.26
ARG RUNTIME_IMAGE=alpine:3.22

FROM --platform=$BUILDPLATFORM ${BASE_IMAGE} AS build-env
WORKDIR /app

# Dependencies as their own layer, so a source edit does not re-download them.
COPY go.mod go.sum ./
RUN go mod download

COPY . ./
# Built WITHOUT `-tags offline`, and that is the security property rather than a
# size saving: the offline throwaway issuer in local_identity.go is guarded by
# that tag, so these binaries physically cannot mint the credentials they would
# then trust. See local_identity_disabled.go.
#
# CGO_ENABLED=0 for a static binary the runtime image needs no libc for.
RUN CGO_ENABLED=0 go build -o out/identity-agent . \
    && CGO_ENABLED=0 go build -o out/crm-server ./crm

FROM ${RUNTIME_IMAGE}
WORKDIR /app
EXPOSE 8006
COPY --from=build-env /app/out/ ./
ENTRYPOINT ["/app/identity-agent"]
