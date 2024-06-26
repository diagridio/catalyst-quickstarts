import express from 'express';
import bodyParser from 'body-parser';
import { DaprClient, CommunicationProtocolEnum} from "@dapr/dapr";

const daprApiToken = process.env.DAPR_API_TOKEN || "";
const appPort = process.env.PORT || 5002; 


const app = express()

const client = new DaprClient({daprApiToken: daprApiToken, communicationProtocol: CommunicationProtocolEnum.HTTP});

app.use(bodyParser.json({ type: '*/*' })) 

app.post('/pubsub/neworders', (req, res) => {
  console.log("Order received: " + JSON.stringify(req.body.data))
  res.sendStatus(200);
});

app.listen(appPort, () => console.log(`server listening at :${appPort}`));
