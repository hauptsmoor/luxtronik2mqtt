# 10: Docker image and CI

**What to build:** A user can run the Bridge with one `docker run`, and every pull request is tested automatically.

- **Image:** a slim Python base, running as a non-root user, with no writable volume and working with a read-only root filesystem. By default it starts the Bridge. The dump-capture command from ticket 01 can be run from the same image.
- **CI:** a GitHub Actions workflow runs the test suite on every pull request and on pushes to `main`.

There's no GitHub remote yet, so the workflow can only be checked by reading it and running the same steps locally until a remote is added.

**Blocked by:** 02 (Tracer bullet: CFI Calculations to MQTT)

**Status:** ready-for-agent

- [x] The image builds locally.
- [x] Started with only `LUX_HOST` and `LUX_MQTT_HOST`, a non-root user and a read-only root filesystem, the container runs the Bridge.
- [x] The capture command runs from the same image and writes the fixture to stdout.
- [x] The container stops cleanly on SIGTERM (and publishes `offline` once ticket 06 is in).
- [x] The CI workflow runs the full test suite on pull requests and on pushes to `main`; its steps pass when run locally.

The workflow hasn't run on GitHub yet: its steps were run locally in `python:3.11-slim` and `python:3.13-slim` containers, as a non-root user like the runner's. Run as root, the two TLS tests fail, because mosquitto drops privileges and can't read pytest's temporary directory.

## Comments

**2026-10-26, from ticket 02:** the test suite starts the mosquitto broker as a subprocess, so the CI job needs `apt-get install mosquitto` (the binary lands in `/usr/sbin`, which `tests/harness.py` also looks in).
