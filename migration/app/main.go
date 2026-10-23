// Command app is the workload the migration quickstart moves from Dapr OSS to
// Catalyst.
//
// One binary, two roles, selected by the ROLE environment variable. It exercises
// the Dapr building blocks that the migration has to preserve: service
// invocation, pub/sub, state, jobs, actors and workflows.
//
//	checkout  - publishes orders, invokes inventory, runs a workflow, schedules a job
//	inventory - hosts the StockActor and serves invocation requests
package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	role := envOr("ROLE", "checkout")
	port := envOr("APP_PORT", "8080")

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	log.Printf("starting role=%s port=%s", role, port)

	var err error
	switch role {
	case "checkout":
		err = runCheckout(ctx, port)
	case "inventory":
		err = runInventory(ctx, port)
	default:
		err = fmt.Errorf("unknown ROLE %q, want checkout or inventory", role)
	}
	if err != nil {
		log.Fatalf("%s: %v", role, err)
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
