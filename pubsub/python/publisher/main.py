from dapr.clients import DaprClient
from cloudevents.sdk.event import v1
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
import os

app = FastAPI()

logging.basicConfig(level=logging.INFO)

class Order(BaseModel):
    orderId: int

pubsub_name = os.getenv('PUBSUB_NAME', 'pubsub')

@app.post('/pubsub/orders')
async def publish_orders(order: Order):
    with DaprClient() as d:
        try:
            result = d.publish_event(
                pubsub_name=pubsub_name,
                topic_name='orders',
                data=order.model_dump_json(),
                data_content_type='application/json',
            )
            logging.info('Publish Successful. Order published: %s' %
                         order.orderId)
            return {'success': True}
        except grpc.RpcError as err:
            logging.error(
                f"Error occurred while publishing order: {err.code()}")

@app.get('/')
async def read_root():
    return {"message": "Publisher is running"}
