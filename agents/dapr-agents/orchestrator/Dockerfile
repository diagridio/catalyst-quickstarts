FROM python:3.12-alpine
WORKDIR /app
EXPOSE 8007
COPY requirements.txt .
RUN apk add --no-cache --virtual .build-deps build-base linux-headers \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps
COPY . .
CMD ["python", "main.py"]
