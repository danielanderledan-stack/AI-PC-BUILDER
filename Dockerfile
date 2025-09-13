FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables (you'll override these in Cloud Run)
ENV DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE"
ENV GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "main_simple.py"]
