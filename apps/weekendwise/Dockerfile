# WeekendWise app container (MVP-03). Built by Cloud Build (make build) and run on Cloud Run (make deploy).
# No credentials are baked in: on Cloud Run the attached service account (weekendwise-run) is used automatically.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code and the bundled seed data (cities, interests, sample trips, simulated conditions). Guides live in Firestore.
COPY weekendwise/ weekendwise/
COPY data/seed/ data/seed/

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001

EXPOSE 8080
# One worker per container; Cloud Run scales out with instances. Shell form so $PORT from Cloud Run is honoured.
CMD exec uvicorn --factory weekendwise.web.server:create_app --host 0.0.0.0 --port "${PORT}" --no-access-log --timeout-graceful-shutdown 20
