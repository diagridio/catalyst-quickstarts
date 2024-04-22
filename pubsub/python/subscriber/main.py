from dapr.clients import DaprClient
from pydantic import BaseModel
from cloudevents.sdk.event import v1
from fastapi import FastAPI, HTTPException
import os
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


@app.post('/pubsub/neworders')
def consume_orders(event: CloudEvent):
    logging.info('Order received : %s' % event.data['orderId'])
    return {'success': True}