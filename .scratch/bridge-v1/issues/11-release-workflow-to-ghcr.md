# 11: Release workflow to GHCR

**What to build:** Releasing is a single command for the maintainer. Pushing a `vX.Y.Z` tag builds the image for amd64, arm64 and armv7 and publishes it to `ghcr.io/<owner>/luxtronik2mqtt`, tagged with the version and `latest`.

There's no GitHub remote yet, so this can only be checked by reading the workflow and doing a local multi-arch build until a remote is added.

**Blocked by:** 10 (Docker image and CI)

**Status:** ready-for-agent

- [x] A `vX.Y.Z` tag triggers the workflow; other pushes don't.
- [x] The workflow builds amd64, arm64 and armv7 and pushes them as one multi-architecture image to GHCR, tagged `X.Y.Z` and `latest`.
- [x] The workflow runs the test suite before building, and fails without publishing if the tests fail.
- [x] A local multi-arch build of the same image succeeds for all three architectures.

The workflow hasn't run on GitHub yet. Locally, a `docker-container` buildx builder (what `setup-buildx-action` creates) built all three platforms, and each platform's image ran `luxtronik2mqtt-capture --help` on a read-only root filesystem under QEMU. The tests run through `ci.yml`, called as a reusable workflow, so pull requests and releases share one definition.
