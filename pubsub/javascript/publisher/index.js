import express from 'express';
import bodyParser from 'body-parser';
import { DaprClient} from "@dapr/dapr";

const pubSubName = process.env.PUBSUB_NAME || "pubsub"; 
const appPort = process.env.PORT || 5001; 

const app = express()

const client = new DaprClient();

app.use(bodyParser.json({ type: '*/*' })) 

//#region Pub/Sub API

app.post('/order', async function (req, res) {
    let order = req.body
    try {
      await client.pubsub.publish(pubSubName, "orders", order);
      console.log("Publish successful. Order published: " + order.orderId);
      res.sendStatus(200);
    } catch (error){
      console.log("Error occurred while publishing order: " + order.orderId);
      res.status(500).send(error);
    }
});


app.listen(appPort, () => console.log(`server listening at :${appPort}`));
