FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal in Phase 1; PDF/export libs (weasyprint etc.)
# get added here in Phase 5 when they're actually needed.
# curl added for the HEALTHCHECK below - it wasn't installed before,
# which meant the healthcheck silently never worked.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# .dockerignore (see that file) excludes .env, so real API keys never
# get copied into the image / baked into a layer.
COPY . .

RUN mkdir -p workspace outputs

# Run as a non-root user - previously this ran as root with no USER
# directive, so anything executed inside the container (including any
# LLM-generated code that ever got run) had full root in the container.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
