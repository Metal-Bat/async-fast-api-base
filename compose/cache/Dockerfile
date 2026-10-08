FROM dragonflydb/dragonfly:v1.27.1

VOLUME ["/data"]

# Keep local development independent of the host CPU count (256 MiB per thread).
ENV CACHE_THREADS=2

CMD ["sh", "-c", "exec dragonfly --requirepass \"$CACHE_PASSWORD\" --dir /data --proactor_threads=\"$CACHE_THREADS\" --logtostderr"]
