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

# Set up required inputs for http client to perform service invocation
base_url = os.getenv('DAPR_HTTP_ENDPOINT', 'http://localhost')
dapr_api_token = os.getenv('DAPR_API_TOKEN', '')
invoke_appid = os.getenv('INVOKE_APPID', 'server')

@app.post('/order')
async def send_order(order: Order):
    headers = {'dapr-app-id': invoke_appid, 'dapr-api-token': dapr_api_token,
               'content-type': 'application/json'}
    try:
        result = requests.post(
            url='%s/neworder' % (base_url),
            data=order.model_dump_json(),
            headers=headers
        )

        if result.ok:
            logging.info('Invocation successful with status code: %s' %
                         result.status_code)
            return {"message": "Invocation successful", "orderId": order.orderId, "targetApp": invoke_appid}
        else:
            logging.error(
                'Error occurred while invoking App ID: %s' % result.reason)
            raise HTTPException(status_code=500, detail={"error": {"code": "INVOCATION_ERROR", "message": "Failed to invoke service"}})

    except Exception as err:
        logging.error(f"Error occurred while invoking service: {err}")
        raise HTTPException(status_code=500, detail={"error": {"code": "INVOCATION_ERROR", "message": "Failed to invoke service"}})

@app.get('/')
async def read_root():
    health_message = "Health check passed. Everything is running smoothly!"
    logging.info("Health check result: %s", health_message)
    return {"status": "healthy", "message": health_message}