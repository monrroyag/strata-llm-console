FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STRATA_CONSOLE_HOST=0.0.0.0 \
    STRATA_CONSOLE_PORT=8090

WORKDIR /app
COPY backend_core.py connection_core.py console_core.py console_server.py history_core.py job_core.py evaluation_core.py ./
COPY optimize_core.py state_store.py telegram_control_bot.py trace_core.py tunnel_core.py update_core.py ./
COPY catalog.json .gitignore README.md ./
COPY configs ./configs
COPY schemas ./schemas
COPY web ./web
COPY docs/languages ./docs/languages
COPY docs/api ./docs/api
COPY data/params_help.json ./data/params_help.json
RUN mkdir -p logs && useradd --create-home --uid 10001 strata \
    && chown -R strata:strata /app
USER strata
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python3 -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3)"
ENTRYPOINT ["python3", "console_server.py"]
