# Usa l'immagine ufficiale di Python come base
FROM python:3.10-slim

# Imposta il maintainer (facoltativo)
LABEL maintainer="tuo_nome@example.com"

# Crea e imposta la directory di lavoro nel container
WORKDIR /app

# Copia il file requirements.txt e installa le dipendenze
COPY requirements.txt .

# Installa le dipendenze senza usare la cache per minimizzare lo spazio
RUN pip install --no-cache-dir -r requirements.txt

# Copia il contenuto della directory 'app' nel container
COPY ./app /app

# Espone la porta su cui FastAPI sarà in esecuzione
EXPOSE 8095

# Comando per avviare l'applicazione FastAPI con Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8095", "--workers", "1"]
