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
    return str(order)

@app.get('/')
async def read_root():
    return {"message": "Server app is running"}