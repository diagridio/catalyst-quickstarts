from pydantic import BaseModel
import logging
from fastapi import FastAPI

app = FastAPI()

logging.basicConfig(level=logging.INFO)


class Order(BaseModel):
    orderId: int

@app.post('/invoke/neworders')
def receive_order(order: Order):
    logging.info('Request received : ' + str(order))
    return str(order)
