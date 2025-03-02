FROM python:3.13.2-slim

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | bash

# Start Ollama in the background and pull the models
RUN ollama serve & sleep 3 && ollama pull llama3.1 && ollama pull deepseek-r1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8501 11434

CMD ollama serve & streamlit run chat-screen.py --server.port=8501 --server.address=0.0.0.0
