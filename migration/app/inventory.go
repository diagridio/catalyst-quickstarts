package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"

	"github.com/dapr/go-sdk/actor"
	"github.com/dapr/go-sdk/client"
	"github.com/dapr/go-sdk/service/common"
	daprd "github.com/dapr/go-sdk/service/http"
)

// StockActor holds per-SKU reserved quantity. Actor state lives in the
// statestore component, which is why that component sets actorStateStore.
type StockActor struct {
	actor.ServerImplBaseCtx

	mu       sync.Mutex
	reserved int
}

// Type is the actor type registered with the placement service.
func (a *StockActor) Type() string { return "StockActor" }

// Reserve adds to the reserved count and returns the running total.
func (a *StockActor) Reserve(ctx context.Context, qty int) (int, error) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.reserved += qty
	log.Printf("ACTOR StockActor/%s reserved=%d", a.ID(), a.reserved)
	return a.reserved, nil
}

// runInventory serves service invocation and hosts the actor type.
func runInventory(ctx context.Context, port string) error {
	s := daprd.NewService(":" + port)

	c, err := client.NewClient()
	if err != nil {
		return fmt.Errorf("create dapr client: %w", err)
	}
	defer c.Close()

	if err := s.AddServiceInvocationHandler("reserve", reserveHandler(c)); err != nil {
		return fmt.Errorf("add reserve handler: %w", err)
	}

	s.RegisterActorImplFactoryContext(func() actor.ServerContext { return &StockActor{} })

	go func() {
		<-ctx.Done()
		_ = s.GracefulStop()
	}()

	log.Printf("inventory listening on :%s", port)
	if err := s.Start(); err != nil {
		return fmt.Errorf("serve: %w", err)
	}
	return nil
}

// reserveHandler is the target of checkout's service invocation call. It calls
// into StockActor so one request exercises invocation and actors together, and
// so actor state lands in the state store.
func reserveHandler(c client.Client) common.ServiceInvocationHandler {
	return func(ctx context.Context, in *common.InvocationEvent) (*common.Content, error) {
		var o order
		if err := json.Unmarshal(in.Data, &o); err != nil {
			return nil, fmt.Errorf("decode order: %w", err)
		}
		log.Printf("INVOKE reserve %s qty=%d", o.SKU, o.Quantity)

		qty, err := json.Marshal(o.Quantity)
		if err != nil {
			return nil, fmt.Errorf("encode quantity: %w", err)
		}
		res, err := c.InvokeActor(ctx, &client.InvokeActorRequest{
			ActorType: "StockActor",
			ActorID:   o.SKU,
			Method:    "Reserve",
			Data:      qty,
		})
		if err != nil {
			return nil, fmt.Errorf("invoke StockActor/%s: %w", o.SKU, err)
		}
		log.Printf("ACTOR StockActor/%s -> %s", o.SKU, string(res.Data))

		reply, err := json.Marshal(map[string]any{"sku": o.SKU, "reserved": json.RawMessage(res.Data)})
		if err != nil {
			return nil, fmt.Errorf("encode reply: %w", err)
		}
		return &common.Content{
			Data:        reply,
			ContentType: "application/json",
		}, nil
	}
}
