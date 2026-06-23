FROM postgres:18.1-bookworm

COPY ./compose/postgres/maintenance /usr/bin/maintenance

RUN chmod +x /usr/bin/maintenance/*

RUN mv /usr/bin/maintenance/* /usr/bin \
    && rmdir /usr/bin/maintenance
