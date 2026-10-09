FROM python:3.14.8-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /bin/uv

WORKDIR /app

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN uv venv /opt/venv

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-default-groups --no-install-project --active \
    && uv pip check --python /opt/venv/bin/python

FROM python:3.14.8-slim-trixie AS runtime

ARG APP_USER=app
ARG APP_HOME=/app

WORKDIR ${APP_HOME}

RUN groupadd --gid 1000 ${APP_USER} \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home ${APP_USER}

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src/ ./src/
RUN pybabel compile -d src/locales -l fa -D messages
COPY pyproject.toml ./
COPY alembic.ini ./

COPY ./compose/backend/start /start
COPY ./compose/backend/start-worker /start-worker
COPY ./compose/backend/start-reporting-worker /start-reporting-worker
COPY ./compose/backend/start-scheduler /start-scheduler
COPY ./compose/backend/start-flower /start-flower
RUN chmod +x /start /start-worker /start-reporting-worker /start-scheduler /start-flower

USER ${APP_USER}
