from dapr.clients import DaprClient
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
import grpc
import requests
import os

app = FastAPI()

logging.basicConfig(level=logging.INFO)

class Order(BaseModel):
    orderId: int

kvstore_name = os.getenv('KVSTORE_NAME', 'kvstore')

@app.get('/')
async def helloworld():
    return {"Hello World"}

@app.post('/kv/orders')
def create_kv(order: Order):
    with DaprClient() as d:
        try:
            d.save_state(store_name=kvstore_name,
                         key=str(order.orderId), value=str(order))
            return {"success": True}
        except grpc.RpcError as err:
            print(f"Error={err.details()}")
            raise HTTPException(status_code=500, detail=err.details())


@app.get('/kv/orders/{orderId}')
def get_kv(orderId: int):
    with DaprClient() as d:
        try:
            kv = d.get_state(kvstore_name, str(orderId))
            return {"data": kv.data}
        except grpc.RpcError as err:
            print(f"Error={err.details()}")
            raise HTTPException(status_code=500, detail=err.details())

@app.delete('/kv/orders/{orderId}')
def delete_kv(orderId: int):
    with DaprClient() as d:
        try:
            d.delete_state(kvstore_name, str(orderId))
            return {'success': True}
        except grpc.RpcError as err:
            print(f"Error={err.details()}")
            raise HTTPException(status_code=500, detail=err.details())
