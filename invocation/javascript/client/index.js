import express from 'express';
import bodyParser from 'body-parser';
import axios from "axios";

const daprApiToken = process.env.DAPR_API_TOKEN || "";
const daprHttpEndpoint = process.env.DAPR_HTTP_ENDPOINT || "http://localhost";
const invokeAppID = process.env.INVOKE_APPID || "target";

const app = express()


app.use(bodyParser.json({ type: '*/*' }))

// Check if process.env.PORT is set
let appPort;
if (process.env.PORT) {
  appPort = parseInt(process.env.PORT);
} else {
  appPort = 5003
  console.warn("Warning: PORT environment variable not set for app. Defaulting to port", appPort);
  console.warn("Note: Using the default port for multiple apps will cause port conflicts.")
}

app.post('/order', async function(req, res) {
  let config = {
    headers: {
      "dapr-app-id": invokeAppID,
      "dapr-api-token": daprApiToken
    }
  };
  let order = req.body

  try {
    await axios.post(`${daprHttpEndpoint}/v1.0/invoke/neworder`, order, config);
    console.log("Invocation successful with status code: %d ", res.statusCode);
    res.sendStatus(200);
  } catch (error) {
    console.log("Error invoking app at " + `${daprHttpEndpoint}/neworder`);
    res.status(500).send(error);
  }

});

app.listen(appPort, () => console.log(`server listening at :${appPort}`));
