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

kvstore_name = os.getenv('STATESTORE_NAME', 'kvstore')

@app.post('/order')
def create_state_item(order: Order):
    with DaprClient() as d:
        try:
            d.save_state(store_name=kvstore_name,
                         key=str(order.orderId), value=str(order))
            print("Save state item successful. Order saved:", str(order))
            return {"success": True}
        except grpc.RpcError as err:
            print(f"Error occurred while saving state item. Exception={err.details()}")
            raise HTTPException(status_code=500, detail=err.details())


@app.get('/order/{orderId}')
def get_state_item(orderId: int):
    with DaprClient() as d:
        try:
            kv = d.get_state(kvstore_name, str(orderId))
            if not kv.data:
                print("State item with orderId does not exist:", str(orderId))
                return {"state item": kv.data}
            else:
                print("Get state item successful. Order retrieved.")
                return {"state item": kv.data}
        
        except grpc.RpcError as err:
            print(f"Error occurred while retrieving state item. Exception={err.details()}")
            raise HTTPException(status_code=500, detail=err.details())

@app.delete('/order/{orderId}')
def delete_state_item(orderId: int):
    with DaprClient() as d:
        try:
            d.delete_state(kvstore_name, str(orderId))
            print('Delete state item successful. Order deleted.')
            return{"success": True}
        except grpc.RpcError as err:
            print(f"Error occurred while retrieving state item. Exception={err.details()}")
            raise HTTPException(status_code=500, detail=err.details())

@app.get('/')
async def read_root():
    return {"message": "Order app is running"}