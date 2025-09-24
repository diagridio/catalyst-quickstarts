from dapr.clients import DaprClient
from pydantic import BaseModel
from cloudevents.sdk.event import v1
from fastapi import FastAPI, HTTPException
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)

class Order(BaseModel):
    orderId: int

class CloudEvent(BaseModel):
    datacontenttype: str
    source: str
    topic: str
    pubsubname: str
    data: dict
    id: str
    specversion: str
    tracestate: str
    type: str
    traceid: str

@app.post('/neworder')
def consume_orders(event: CloudEvent):
    order_id = event.data.get('orderId') or event.data.get('key')
    if order_id:
        logging.info('Order received: %s' % order_id)
        return {"message": "Message received successfully", "orderId": order_id}
    else:
        logging.error('Missing key in event data: orderId or key')
        raise HTTPException(status_code=400, detail={"error": {"code": "MISSING_ORDER_ID", "message": "Missing key in event data: orderId or key"}})

@app.get('/')
async def read_root():
    health_message = "Health check passed. Everything is running smoothly!"
    logging.info("Health check result: %s", health_message)
    return {"status": "healthy", "message": health_message}
