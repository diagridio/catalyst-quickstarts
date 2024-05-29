FROM --platform=$BUILDPLATFORM golang:latest AS build
WORKDIR /src
COPY . .
RUN go mod download
ARG TARGETOS TARGETARCH
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -a -installsuffix cgo -o publisherApp .

FROM --platform=$BUILDPLATFORM alpine:latest AS final
WORKDIR /root/

COPY --from=build /src/publisherApp .

EXPOSE 5001
ENV PORT 5001

CMD ["./publisherApp"]