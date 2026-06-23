FROM python:3.14-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /bin/uv

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN uv venv /opt/venv

COPY pyproject.toml ./

RUN uv pip install --python=/opt/venv/bin/python -r pyproject.toml

FROM python:3.14-slim-trixie AS runtime

ARG APP_USER=app
ARG APP_HOME=/app

WORKDIR ${APP_HOME}

RUN groupadd --gid 1000 ${APP_USER} \
    && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home ${APP_USER}

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src/ ./src/
COPY pyproject.toml ./
COPY alembic.ini ./

COPY ./compose/backend/start /start
RUN chmod +x /start

USER ${APP_USER}
