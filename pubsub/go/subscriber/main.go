package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"

	dapr "github.com/dapr/go-sdk/client"
	"github.com/gin-gonic/gin"
)

const PUB_SUB_NAME = "pubsub"
const TOPIC_NAME = "orders"

type Order struct {
	OrderId int `json:"orderId"`
}

var client dapr.Client

func main() {

	// Initialize the Dapr client
	client, err := dapr.NewClient()
	if err != nil {
		log.Fatalf("Error creating dapr client: %v", err)
	}
	defer client.Close()

	router := gin.Default()

	router.POST("/pubsub/neworders", consumeOrders)

	router.Run("localhost:5001")
}

func consumeOrders(c *gin.Context) {
	var order Order
	// Call BindJSON to bind the received JSON to
	// order.
	if err := c.BindJSON(&order); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	}

	//marshall order to save to state store
	data, err := json.Marshal(order)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	}

	ctx := context.Background()
	err = client.PublishEvent(ctx, PUB_SUB_NAME, TOPIC_NAME, data, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	}

	c.JSON(http.StatusOK, gin.H{"success": true})
}
