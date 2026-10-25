# 11: Release workflow to GHCR

**What to build:** Releasing is a single command for the maintainer. Pushing a `vX.Y.Z` tag builds the image for amd64, arm64 and armv7 and publishes it to `ghcr.io/<owner>/luxtronik2mqtt`, tagged with the version and `latest`.

There's no GitHub remote yet, so this can only be checked by reading the workflow and doing a local multi-arch build until a remote is added.

**Blocked by:** 10 (Docker image and CI)

**Status:** ready-for-agent

- [ ] A `vX.Y.Z` tag triggers the workflow; other pushes don't.
- [ ] The workflow builds amd64, arm64 and armv7 and pushes them as one multi-architecture image to GHCR, tagged `X.Y.Z` and `latest`.
- [ ] The workflow runs the test suite before building, and fails without publishing if the tests fail.
- [ ] A local multi-arch build of the same image succeeds for all three architectures.
