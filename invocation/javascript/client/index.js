import express from "express";
import bodyParser from "body-parser";
import axios from "axios";

const daprApiToken = process.env.DAPR_API_TOKEN || "";
const daprHttpEndpoint = process.env.DAPR_HTTP_ENDPOINT || "http://localhost";
const invokeAppID = process.env.INVOKE_APPID || "server";
const appPort = process.env.PORT || 5001;

const app = express();

app.use(bodyParser.json({ type: "*/*" }));

// Health check endpoint
app.get("/", (req, res) => {
  const healthMessage =
    "Health check passed. Everything is running smoothly! 🚀";
  console.log("Health check result: %s", healthMessage);
  res.status(200).json({ status: "healthy", message: healthMessage });
});

app.post("/order", async function (req, res) {
  let config = {
    headers: {
      "dapr-app-id": invokeAppID,
      "dapr-api-token": daprApiToken,
    },
  };
  let order = req.body;

  try {
    const response = await axios.post(
      `${daprHttpEndpoint}/neworder`,
      order,
      config
    );
    console.log("Invocation successful with status code: %d ", response.status);
    res.status(200).json({
      message: "Invocation successful",
      orderId: order.orderId,
      targetApp: invokeAppID,
    });
  } catch (error) {
    console.log("Error invoking app at " + `${daprHttpEndpoint}/neworder`);
    res.status(500).json({
      error: {
        code: "INVOCATION_ERROR",
        message: "Failed to invoke service",
      },
    });
  }
});

app.listen(appPort, () => console.log(`server listening at :${appPort}`));
