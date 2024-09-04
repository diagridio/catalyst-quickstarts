import express from 'express';
import bodyParser from 'body-parser';
import { DaprClient, CommunicationProtocolEnum} from "@dapr/dapr";

const appPort = process.env.PORT || 5001; 
const daprApiToken = process.env.DAPR_API_TOKEN || "";
const stateStoreName = process.env.STATESORE_NAME || "kvstore"; 

const app = express()

const client = new DaprClient({daprApiToken: daprApiToken, communicationProtocol: CommunicationProtocolEnum.HTTP});

app.use(bodyParser.json({ type: '*/*' })) 

app.post('/order', async function (req, res) {
  req.accepts('application/json')

  const keyName = "order" + req.body.orderId
  const state = [
    {
      key: keyName,
      value: req.body
    }]

  try {
    await client.state.save(stateStoreName, state);
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
    console.log("Get state item successful. Order retrieved: ", order)
    res.json(order)
  } catch (error) {
    console.log("Error occurred while retrieving state item: " + req.params.orderId);
    res.status(500).send(error);
  }
});

app.delete('/order/:orderId', async function (req, res) {
  const keyName = "order" + req.params.orderId
  try {
    await client.state.delete(stateStoreName, keyName)
    console.log("Delete state item successful. Order deleted: ", req.params.orderId)
    res.sendStatus(200);
  } catch (error) {
    console.log("Error occurred while deleting state item: " + req.params.orderId);
    res.status(500).send(error);
  }
});


app.listen(appPort, () => console.log(`server listening at :${appPort}`));