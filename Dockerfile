FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# GOOGLE_API_KEY is provided at runtime (docker run -e / Cloud Run env var),
# never baked into the image.
ENTRYPOINT ["python", "-m", "app.cli"]
CMD ["--topic", "Photosynthesis"]
