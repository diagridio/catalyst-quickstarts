import express from 'express';
import bodyParser from 'body-parser';

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

app.post('/invoke/neworders', (req, res) => {
  console.log("Request received: %s", JSON.stringify(req.body))
  res.sendStatus(200);
});

app.listen(appPort, () => console.log(`server listening at :${appPort}`));
