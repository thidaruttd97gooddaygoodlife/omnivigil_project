FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

ARG INSTALL_ML=false
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN if [ "$INSTALL_ML" = "true" ]; then \
      pip install --no-cache-dir --index-url "$TORCH_INDEX_URL" torch && \
      pip install --no-cache-dir chronos-forecasting; \
    fi

COPY app ./app

EXPOSE 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
