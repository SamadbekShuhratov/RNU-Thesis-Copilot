FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RNU_HOST=0.0.0.0 RNU_DATA_DIR=/data
# LibreOffice gives exact page counts for the 4–6 page Science Week limit (optional, ~400 MB)
ARG WITH_LIBREOFFICE=1
RUN if [ "$WITH_LIBREOFFICE" = "1" ]; then apt-get update && apt-get install -y --no-install-recommends libreoffice-writer && rm -rf /var/lib/apt/lists/*; fi
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8765
VOLUME ["/data"]
CMD ["python", "-m", "app", "--no-browser"]
