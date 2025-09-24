import express from "express";
import bodyParser from "body-parser";
import { DaprClient } from "@dapr/dapr";

const pubSubName = process.env.PUBSUB_NAME || "pubsub";
const appPort = process.env.PORT || 5001;

const app = express();

const client = new DaprClient();

app.use(bodyParser.json({ type: "*/*" }));

//#region Pub/Sub API

// Health check endpoint
app.get("/", (req, res) => {
  const healthMessage =
    "Health check passed. Everything is running smoothly! 🚀";
  console.log("Health check result: %s", healthMessage);
  res.status(200).json({ status: "healthy", message: healthMessage });
});

app.post("/order", async function (req, res) {
  let order = req.body;
  try {
    const publishResponse = await client.pubsub.publish(
      pubSubName,
      "orders",
      order
    );
    if (publishResponse.error) {
      throw publishResponse.error.message;
    }
    console.log("Publish successful. Order published: " + order.orderId);
    res.status(201).json({
      id: order.orderId,
      message: "Message published successfully",
      topic: "orders",
    });
  } catch (error) {
    console.log("Error occurred while publishing order: " + order.orderId);
    res.status(500).json({
      error: { code: "PUBLISH_ERROR", message: "Failed to publish message" },
    });
  }
});

app.listen(appPort, () => console.log(`server listening at :${appPort}`));
