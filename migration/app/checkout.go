package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/dapr/go-sdk/client"
)

const (
	pubsubName   = "orderpubsub"
	ordersTopic  = "orders"
	stateStore   = "statestore"
	inventoryApp = "inventory"
)

// order is the payload carried across pub/sub, invocation and the workflow.
type order struct {
	ID       string `json:"id"`
	SKU      string `json:"sku"`
	Quantity int    `json:"quantity"`
}

// runCheckout serves the pub/sub route declared by the Subscription resource,
// the jobs callback, and a manual trigger that drives one order through every
// building block.
func runCheckout(ctx context.Context, port string) error {
	c, err := client.NewClient()
	if err != nil {
		return fmt.Errorf("create dapr client: %w", err)
	}
	defer c.Close()

	wfDone, err := startWorkflowWorker()
	if err != nil {
		return fmt.Errorf("start workflow worker: %w", err)
	}
	defer wfDone()

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	// Route declared by the order-updates Subscription resource. Dapr delivers a
	// CloudEvent envelope here; we only care that delivery still happens after
	// the migration, so the body is logged rather than deeply parsed.
	mux.HandleFunc("/orders", func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		log.Printf("PUBSUB received on /orders: %s", string(body))
		w.WriteHeader(http.StatusOK)
	})

	// Jobs API callback. Dapr posts to /job/<name> when a scheduled job fires.
	mux.HandleFunc("/job/restock", func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		log.Printf("JOB fired restock: %s", string(body))
		w.WriteHeader(http.StatusOK)
	})

	// Manual trigger: exercises every building block once.
	mux.HandleFunc("/start", func(w http.ResponseWriter, r *http.Request) {
		o := order{ID: fmt.Sprintf("order-%d", time.Now().Unix()), SKU: "widget", Quantity: 2}
		if err := driveOnce(r.Context(), c, o); err != nil {
			log.Printf("drive failed: %v", err)
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]string{"started": o.ID})
	})

	srv := &http.Server{Addr: ":" + port, Handler: mux}
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdownCtx)
	}()

	log.Printf("checkout listening on :%s", port)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return fmt.Errorf("serve: %w", err)
	}
	return nil
}

// driveOnce walks one order through state, invocation, pub/sub, jobs and a
// workflow, logging each step so a migration run can be checked by eye.
func driveOnce(ctx context.Context, c client.Client, o order) error {
	payload, err := json.Marshal(o)
	if err != nil {
		return fmt.Errorf("marshal order: %w", err)
	}

	if err := c.SaveState(ctx, stateStore, o.ID, payload, nil); err != nil {
		return fmt.Errorf("save state: %w", err)
	}
	log.Printf("STATE saved %s", o.ID)

	resp, err := c.InvokeMethodWithContent(ctx, inventoryApp, "reserve", http.MethodPost, &client.DataContent{
		Data:        payload,
		ContentType: "application/json",
	})
	if err != nil {
		return fmt.Errorf("invoke %s/reserve: %w", inventoryApp, err)
	}
	log.Printf("INVOKE inventory/reserve -> %s", string(resp))

	if err := c.PublishEvent(ctx, pubsubName, ordersTopic, payload); err != nil {
		return fmt.Errorf("publish %s/%s: %w", pubsubName, ordersTopic, err)
	}
	log.Printf("PUBSUB published %s", o.ID)

	if err := scheduleRestock(ctx, c, o); err != nil {
		return fmt.Errorf("schedule job: %w", err)
	}

	id, err := startOrderWorkflow(ctx, o)
	if err != nil {
		return fmt.Errorf("start workflow: %w", err)
	}
	log.Printf("WORKFLOW started %s", id)
	return nil
}
