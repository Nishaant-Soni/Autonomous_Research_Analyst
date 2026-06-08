FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache

WORKDIR /srv

# Install sentence-transformers and bake the embedding model weights into the image
# (PRD §7) BEFORE copying app code, so editing app code never re-downloads the model.
RUN pip install --upgrade pip && pip install "sentence-transformers>=3.0"
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

# Install the app and its remaining dependencies.
COPY pyproject.toml ./
COPY app ./app
RUN pip install ".[eval]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
