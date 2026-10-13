# Build stage
FROM golang:1.22-alpine AS builder

WORKDIR /app

# Copy go module files
COPY tenapp/go.mod tenapp/go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY tenapp/ ./

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o voice-assistant main.go

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY ten_packages/extension/main_python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ten_packages/extension/openai_llm2_python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend build
COPY --from=builder /app/tenapp ./tenapp

# Copy API server
COPY ten_apps/api_server ./ten_apps/api_server

# Copy frontend
COPY ten_apps/voice-assistant ./ten_apps/voice-assistant

# Copy built application
COPY --from=builder /app/voice-assistant .

# Expose ports
EXPOSE 8080 3000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["sh", "-c", "python ten_apps/api_server/main.py & npm run dev --prefix ten_apps/voice-assistant & ./voice-assistant"]
