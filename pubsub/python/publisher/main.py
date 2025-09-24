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
topic_name = os.getenv('TOPIC_NAME', 'orders')

@app.post('/order', status_code=201)
async def publish_orders(order: Order):
    with DaprClient() as d:
        try:
            result = d.publish_event(
                pubsub_name=pubsub_name,
                topic_name=topic_name,
                data=order.model_dump_json(),
                data_content_type='application/json',
            )
            logging.info('Publish successful. Order published: %s' %
                         order.orderId)
            return {"id": order.orderId, "message": "Message published successfully", "topic": "orders"}
        except grpc.RpcError as err:
            logging.error(
                f"Error occurred while publishing order: {err.code()}")
            raise HTTPException(status_code=500, detail={"error": {"code": "PUBLISH_ERROR", "message": "Failed to publish message"}})

@app.get('/')
async def read_root():
    health_message = "Health check passed. Everything is running smoothly!"
    logging.info("Health check result: %s", health_message)
    return {"status": "healthy", "message": health_message}
