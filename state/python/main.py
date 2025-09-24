from dapr.clients import DaprClient
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import logging
import grpc
import requests
import os

app = FastAPI()

logging.basicConfig(level=logging.INFO)

class Order(BaseModel):
    orderId: int

statestore_name = os.getenv('STATESTORE_NAME', 'statestore')

@app.post('/order', status_code=201)
def create_state_item(order: Order):
    with DaprClient() as d:
        try:
            d.save_state(store_name=statestore_name,
                         key=str(order.orderId), value=str(order))
            logging.info('Save state item successful. Order saved with key: %s and value: %s' % (str(order.orderId), str(order)))
            return {"id": order.orderId, "message": "Order created successfully"}
        except grpc.RpcError as err:
            logging.info('Error occurred while saving state item %s. Exception= %' % (str(order.orderId), {err.details()}))
            raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": "An internal server error occurred"}})


@app.get('/order/{orderId}')
def get_state_item(orderId: int):
    with DaprClient() as d:
        try:
            kv = d.get_state(statestore_name, str(orderId))
            if not kv.data:
                logging.info('State item with key %s does not exist' % str(orderId))
                raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": f"Order with id '{orderId}' not found"}})
            else:
                logging.info('Get state item successful. Order retrieved: %s' % str(orderId))
                return {"data": kv.data}
        
        except grpc.RpcError as err:
            logging.info('Error occurred while retrieving state item: %s. Exception= %s' % (str(orderId), {err.details()}))
            raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": "An internal server error occurred"}})

@app.delete('/order/{orderId}')
def delete_state_item(orderId: int):
    with DaprClient() as d:
        try:
            d.delete_state(statestore_name, str(orderId))
            logging.info('Delete state item successful. Order deleted: %s' % str(orderId))
            return Response(status_code=204)
        except grpc.RpcError as err:
            logging.info('Error occurred while deleting state item:  %s. Exception= %s' % (str(orderId),{err.details()}))
            raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL_ERROR", "message": "An internal server error occurred"}})

@app.get('/')
async def read_root():
    health_message = "Health check passed. Everything is running smoothly!"
    logging.info("Health check result: %s", health_message)
    return {"status": "healthy", "message": health_message}