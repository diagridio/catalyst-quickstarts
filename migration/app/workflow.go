package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"github.com/dapr/go-sdk/client"
	"github.com/dapr/go-sdk/workflow"
	"google.golang.org/protobuf/types/known/anypb"
	"google.golang.org/protobuf/types/known/wrapperspb"
)

// startWorkflowWorker registers the order workflow and its activity. The
// returned func stops the worker.
func startWorkflowWorker() (func(), error) {
	w, err := workflow.NewWorker()
	if err != nil {
		return nil, fmt.Errorf("new worker: %w", err)
	}
	if err := w.RegisterWorkflow(OrderWorkflow); err != nil {
		return nil, fmt.Errorf("register workflow: %w", err)
	}
	if err := w.RegisterActivity(ChargeActivity); err != nil {
		return nil, fmt.Errorf("register activity: %w", err)
	}
	if err := w.Start(); err != nil {
		return nil, fmt.Errorf("start worker: %w", err)
	}
	log.Print("WORKFLOW worker started")
	return func() { _ = w.Shutdown() }, nil
}

// OrderWorkflow is deliberately trivial. Its value here is that it creates
// durable state in the scheduler, which is exactly what does not migrate.
func OrderWorkflow(ctx *workflow.WorkflowContext) (any, error) {
	var o order
	if err := ctx.GetInput(&o); err != nil {
		return nil, fmt.Errorf("workflow input: %w", err)
	}

	var charged string
	if err := ctx.CallActivity(ChargeActivity, workflow.ActivityInput(o)).Await(&charged); err != nil {
		return nil, fmt.Errorf("charge activity: %w", err)
	}
	return charged, nil
}

// ChargeActivity stands in for a real side effect.
func ChargeActivity(ctx workflow.ActivityContext) (any, error) {
	var o order
	if err := ctx.GetInput(&o); err != nil {
		return nil, fmt.Errorf("activity input: %w", err)
	}
	log.Printf("ACTIVITY charged %s qty=%d", o.ID, o.Quantity)
	return fmt.Sprintf("charged:%s", o.ID), nil
}

// startOrderWorkflow schedules one workflow instance and returns its id.
func startOrderWorkflow(ctx context.Context, o order) (string, error) {
	wfClient, err := workflow.NewClient()
	if err != nil {
		return "", fmt.Errorf("workflow client: %w", err)
	}
	id, err := wfClient.ScheduleNewWorkflow(ctx, "OrderWorkflow", workflow.WithInput(o))
	if err != nil {
		return "", fmt.Errorf("schedule workflow: %w", err)
	}
	return id, nil
}

// scheduleRestock creates a Jobs API job. Jobs live in the Dapr scheduler and
// are named in cut-over.mdx as state that does not survive the migration.
func scheduleRestock(ctx context.Context, c client.Client, o order) error {
	payload, err := json.Marshal(o)
	if err != nil {
		return fmt.Errorf("marshal job payload: %w", err)
	}
	data, err := anypb.New(wrapperspb.String(string(payload)))
	if err != nil {
		return fmt.Errorf("wrap job payload: %w", err)
	}
	dueTime := "30s"
	job := &client.Job{
		Name:    "restock",
		Data:    data,
		DueTime: &dueTime,
	}
	if err := c.ScheduleJobAlpha1(ctx, job); err != nil {
		return fmt.Errorf("schedule job restock: %w", err)
	}
	log.Print("JOB scheduled restock")
	return nil
}
