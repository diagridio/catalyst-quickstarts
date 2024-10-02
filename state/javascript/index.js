import express from 'express';
import bodyParser from 'body-parser';
import { DaprClient} from "@dapr/dapr";

const appPort = process.env.PORT || 5001; 
const stateStoreName = process.env.STATESTORE_NAME || "kvstore"; 

const app = express()

const client = new DaprClient();

app.use(bodyParser.json({ type: '*/*' })) 

// Health check endpoint
app.get('/', (req, res) => {
  const healthMessage = "Health check passed. Everything is running smoothly! 🚀";
  console.log("Health check result: %s", healthMessage);
  res.status(200).send(healthMessage);
});

app.post('/order', async function (req, res) {
  req.accepts('application/json')

  const keyName = "order" + req.body.orderId
  const state = [
    {
      key: keyName,
      value: req.body
    }]

  try {
    const saveResponse = await client.state.save(stateStoreName, state);
    if (saveResponse.error) {
        throw saveResponse.error.message;
    }
    console.log("Save state item successful. Order saved: " + req.body.orderId);
    res.sendStatus(200);
  } catch (error) {
    console.log("Error occurred while saving state item: " + req.body.orderId);
    res.status(500).send(error);
  }
});

app.get('/order/:orderId', async function (req, res) {
  const keyName = "order" + req.params.orderId
  try {
    const order = await client.state.get(stateStoreName, keyName)
    console.log(order)
    if(!order) {      
      console.log("State item with key does not exist: " + keyName);
      res.status(200);
    }
    else {
      console.log("Get state item successful. Order retrieved: ", order )
      res.json(order)
    }
  } catch (error) {
    console.log("Error occurred while retrieving state item: " + req.params.orderId);
    res.status(500).send(error);
  }
});

app.delete('/order/:orderId', async function (req, res) {
  const keyName = "order" + req.params.orderId
  try {
    const deleteResponse = await client.state.delete(stateStoreName, keyName)
    if (deleteResponse.error) {
        throw deleteResponse.error.message;
    }
    console.log("Delete state item successful. Order deleted: ", req.params.orderId)
    res.sendStatus(200);
  } catch (error) {
    console.log("Error occurred while deleting state item: " + req.params.orderId);
    res.status(500).send(error);
  }
});


app.listen(appPort, () => console.log(`server listening at :${appPort}`));
