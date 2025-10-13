FROM docker.io/python:3.13.8-slim-bookworm as python

ARG BUILD_ENVIRONMENT=local
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV BUILD_ENV ${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

RUN apt-get update && apt-get install --no-install-recommends -y \
  sudo \
  git \
  bash-completion \
  vim \
  curl \
  ca-certificates \
  ssh

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

RUN groupadd --gid 1000 dev-user \
  && useradd --uid 1000 --gid dev-user --shell /bin/bash --create-home dev-user \
  && echo dev-user ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/dev-user \
  && chmod 0440 /etc/sudoers.d/dev-user

COPY ./requirements .
RUN uv pip install --system -r ${BUILD_ENVIRONMENT}.txt

RUN apt-get update && apt-get install --no-install-recommends -y \
  libpq-dev \
  gettext \
  binutils libproj-dev gdal-bin \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

COPY ./compose/local/backend/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/local/backend/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

RUN mkdir -p ${APP_HOME}/logs
COPY . ${APP_HOME}

ENTRYPOINT ["/entrypoint"]
