# 10: Docker image and CI

**What to build:** A user can run the Bridge with one `docker run`, and every pull request is tested automatically.

- **Image:** a slim Python base, running as a non-root user, with no writable volume and working with a read-only root filesystem. By default it starts the Bridge. The dump-capture command from ticket 01 can be run from the same image.
- **CI:** a GitHub Actions workflow runs the test suite on every pull request and on pushes to `main`.

There's no GitHub remote yet, so the workflow can only be checked by reading it and running the same steps locally until a remote is added.

**Blocked by:** 02 (Tracer bullet: CFI Calculations to MQTT)

**Status:** ready-for-agent

- [ ] The image builds locally.
- [ ] Started with only `LUX_HOST` and `LUX_MQTT_HOST`, a non-root user and a read-only root filesystem, the container runs the Bridge.
- [ ] The capture command runs from the same image and writes the fixture to stdout.
- [ ] The container stops cleanly on SIGTERM (and publishes `offline` once ticket 06 is in).
- [ ] The CI workflow runs the full test suite on pull requests and on pushes to `main`; its steps pass when run locally.
