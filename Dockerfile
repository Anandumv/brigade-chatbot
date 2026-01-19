FROM python:3.9-slim

# Install FFmpeg and build dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libgl1 \
    libglib2.0-0 \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt && pip install pixeltable==0.2.30

# Copy application code
COPY backend/ .

# Expose port
EXPOSE 8000

# Hardcoded Environment Variables (Fallback for Injection Failure)
ENV OPENAI_API_KEY=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
ENV OPENAI_BASE_URL=https://openrouter.ai/api/v1
ENV TAVILY_API_KEY=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
ENV LLM_MODEL=openai/gpt-4-turbo-preview
ENV USE_PIXELTABLE=true
ENV ENVIRONMENT=production
ENV PIXELTABLE_DB_URL=postgresql://postgres:AKuorrtAicoZpKSRvCsbCpWMuCwoEblk@postgres.railway.internal:5432/railway

# Run the application
# Run the application (Shell form to expand $PORT)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --loop asyncio
