import express from 'express';
import bodyParser from 'body-parser';

const appPort = process.env.PORT || 5002; 

const app = express()

app.use(bodyParser.json({ type: '*/*' }))


app.post('/neworder', (req, res) => {
  console.log("Invocation received with data: %s", JSON.stringify(req.body))
  res.sendStatus(200);
});

app.listen(appPort, () => console.log(`server listening at :${appPort}`));
