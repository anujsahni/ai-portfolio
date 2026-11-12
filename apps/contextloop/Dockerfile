# The contextloop application image: every job and long-running service of the demo runs from it
# with a different command. Builds for linux/arm64 and linux/amd64. No secrets in any layer.
FROM python:3.12.16-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv==0.13.7

# Two environments (see the header of each requirements file):
#   /opt/venv      main: dbt, MetricFlow, dbt-mcp, MCP servers, agent, app
#   /opt/fivetran  Fivetran Connector SDK, used only by the sync job
COPY requirements.txt requirements-connector.txt /tmp/
RUN uv venv /opt/venv \
 && VIRTUAL_ENV=/opt/venv uv pip install -r /tmp/requirements.txt \
 && uv venv /opt/fivetran \
 && VIRTUAL_ENV=/opt/fivetran uv pip install -r /tmp/requirements-connector.txt \
 && rm /tmp/requirements*.txt

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app \
    DBT_PROFILES_DIR=/app/dbt/contextloop \
    DBT_PROJECT_DIR=/app/dbt/contextloop

RUN useradd --create-home --uid 1000 app \
 && mkdir -p /warehouse /app/data/out \
 && chown -R app:app /warehouse /app

WORKDIR /app
COPY --chown=app:app . /app
# dbt artifacts live on the warehouse volume so every service sees the latest build; MetricFlow (mf) reads ./target.
RUN ln -sfn /warehouse/dbt_target /app/dbt/contextloop/target
USER app
# DuckDB extensions for reading Iceberg from object storage, installed at build time so the demo runs offline.
RUN python -c "import duckdb; c = duckdb.connect(); [c.install_extension(e) for e in ('iceberg', 'httpfs', 'avro')]"

CMD ["python", "-m", "contextloop.cli", "--help"]
