import express from 'express';
import bodyParser from 'body-parser';
import { DaprClient, CommunicationProtocolEnum} from "@dapr/dapr";

const pubSubName = process.env.PUBSUB_NAME || "pubsub"; 
const appPort = process.env.PORT || 5001; 

const app = express()

const daprApiToken = process.env.DAPR_API_TOKEN || "";

const client = new DaprClient({daprApiToken: daprApiToken, communicationProtocol: CommunicationProtocolEnum.HTTP});

app.use(bodyParser.json({ type: '*/*' })) 

//#region Pub/Sub API

app.post('/pubsub/orders', async function (req, res) {
    let order = req.body
    try {
      await client.pubsub.publish(pubSubName, "orders", order);
      console.log("Published data: " + order.orderId);
      res.sendStatus(200);
    } catch (error){
      console.log("Error publishing order: " + order.orderId);
      res.status(500).send(error);
    }
});


app.listen(appPort, () => console.log(`server listening at :${appPort}`));
