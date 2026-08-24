FROM python:3.11-slim
WORKDIR /app
RUN mkdir -p /opt/kvstore/data
COPY primary.py replica.py kvlogger.py ./
ENV ROLE=primary
ENV PORT=5000
ENV REPLICA_HOST=127.0.0.1
ENV REPLICA_PORT=5001
ENV WAL_FILE=/opt/kvstore/data/wal.log
CMD ["sh", "-c", "if [ \"$ROLE\" = \"primary\" ]; then python3 -u primary.py; else python3 -u replica.py; fi"]