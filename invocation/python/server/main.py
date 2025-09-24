from pydantic import BaseModel
import logging
from fastapi import FastAPI

app = FastAPI()

logging.basicConfig(level=logging.INFO)


class Order(BaseModel):
    orderId: int

@app.post('/neworder')
def receive_order(order: Order):
    logging.info('Invocation received with data: ' + str(order))
    return {"message": "Order received successfully", "orderId": order.orderId}

@app.get('/')
async def read_root():
    health_message = "Health check passed. Everything is running smoothly!"
    logging.info("Health check result: %s", health_message)
    return {"status": "healthy", "message": health_message}