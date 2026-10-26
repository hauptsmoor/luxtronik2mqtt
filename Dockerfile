# The Bridge, and the dump-capture command, in one image.
#   docker run -e LUX_HOST=... -e LUX_MQTT_HOST=... luxtronik2mqtt
#   docker run --rm luxtronik2mqtt luxtronik2mqtt-capture <controller> > fixture.json

# Also the newest Python in the CI matrix (.github/workflows/ci.yml).
ARG PYTHON_VERSION=3.13

# git only to fetch python-luxtronik, which is pinned to a commit (ADR 0002).
FROM python:${PYTHON_VERSION}-slim AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
COPY pyproject.toml README.md LICENSE /src/
COPY src /src/src
RUN /opt/venv/bin/pip install --no-cache-dir /src \
    && /opt/venv/bin/python -m compileall -q /opt/venv

FROM python:${PYTHON_VERSION}-slim
COPY --from=build /opt/venv /opt/venv
# The root filesystem may be read-only, and the Bridge writes nothing to disk.
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 65534:65534
# Exec form, so the Bridge is PID 1 and gets the SIGTERM from `docker stop`.
CMD ["luxtronik2mqtt"]
