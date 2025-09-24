import express from "express";
import bodyParser from "body-parser";

const appPort = process.env.PORT || 5002;

const app = express();

app.use(bodyParser.json({ type: "*/*" }));

// Health check endpoint
app.get("/", (req, res) => {
  const healthMessage =
    "Health check passed. Everything is running smoothly! 🚀";
  console.log("Health check result: %s", healthMessage);
  res.status(200).json({ status: "healthy", message: healthMessage });
});

app.post("/neworder", (req, res) => {
  console.log("Order received: " + JSON.stringify(req.body.data));
  const orderId = req.body.data?.orderId || req.body.orderId;
  res
    .status(200)
    .json({ message: "Message received successfully", orderId: orderId });
});

app.listen(appPort, () => console.log(`server listening at :${appPort}`));
