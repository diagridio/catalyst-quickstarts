module github.com/diagridio/catalyst-quickstarts/migration

go 1.24.6

// Pinned to v1.13.0 deliberately: the go-sdk dropped the `workflow` package in
// v1.14, and this app needs workflow authoring and the jobs API together.
require (
	github.com/dapr/go-sdk v1.13.0
	google.golang.org/protobuf v1.36.6
)

require (
	github.com/cenkalti/backoff/v4 v4.3.0 // indirect
	github.com/dapr/dapr v1.16.0 // indirect
	github.com/dapr/durabletask-go v0.10.0 // indirect
	github.com/dapr/kit v0.16.1 // indirect
	github.com/go-chi/chi/v5 v5.2.2 // indirect
	github.com/go-logr/logr v1.4.2 // indirect
	github.com/go-logr/stdr v1.2.2 // indirect
	github.com/google/uuid v1.6.0 // indirect
	go.opentelemetry.io/auto/sdk v1.1.0 // indirect
	go.opentelemetry.io/otel v1.36.0 // indirect
	go.opentelemetry.io/otel/metric v1.36.0 // indirect
	go.opentelemetry.io/otel/trace v1.36.0 // indirect
	golang.org/x/net v0.41.0 // indirect
	golang.org/x/sys v0.33.0 // indirect
	golang.org/x/text v0.26.0 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20250603155806-513f23925822 // indirect
	google.golang.org/grpc v1.73.0 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
)
