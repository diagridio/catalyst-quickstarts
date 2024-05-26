package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"strconv"

	dapr "github.com/dapr/go-sdk/client"
	"github.com/gin-gonic/gin"
)

const STATE_STORE_NAME = "statestore"

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

	router.GET("/", helloWorld)
	router.POST("/kv/orders", createKV)
	router.GET("/kv/orders/:id", getKV)
	router.DELETE("/kv/orders/:id", deleteKV)

	router.Run("localhost:8080")
}

// Test hello-world endpoint
func helloWorld(c *gin.Context) {
	c.IndentedJSON(http.StatusOK, gin.H{"message": "Hello World"})
}

func createKV(c *gin.Context) {
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
	err = client.SaveState(ctx, STATE_STORE_NAME, strconv.Itoa(order.OrderId), data, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
	}

	c.JSON(http.StatusOK, gin.H{"success": true})
}

func getKV(c *gin.Context) {
	ctx := context.Background()

	id := c.Param("id")

	item, err := client.GetState(ctx, STATE_STORE_NAME, id, nil)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"message": "Not Found"})
	}
	c.IndentedJSON(http.StatusOK, item.Value)
}

func deleteKV(c *gin.Context) {
	ctx := context.Background()

	id := c.Param("id")

	err := client.DeleteState(ctx, STATE_STORE_NAME, id, nil)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"message": "Not Found"})
	}
	c.JSON(http.StatusOK, gin.H{"success": true})
}
