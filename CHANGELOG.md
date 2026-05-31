# Changelog

## 0.2.0 - 2026-05-31

### Added
- FastAPI gateway framework scaffold with config-driven proxy routing.
- Administrative portal and dashboard with scalable frontend assets.
- Runtime configuration editing endpoints.
- API key lifecycle management (create, list, revoke) and optional route protection.
- In-memory response caching with TTL and max-entry controls.
- Containerization support via Dockerfile and Docker/Podman Makefile workflow.
- GitHub Actions test workflow and Dependabot configuration.
- Test suite covering configuration, proxy behavior, admin endpoints, and caching.

### Changed
- Replaced deprecated FastAPI startup/shutdown `on_event` handlers with lifespan.
- Migrated admin portal tests away from deprecated TestClient usage.

### Notes
- The generated API keys file is intentionally gitignored (`config/api_keys.json`).
