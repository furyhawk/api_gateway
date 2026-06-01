# Changelog

## 0.2.1 - 2026-06-01

### Added
- Companion backend route-parity checker with a dedicated test module.
- Integrated dev compose workflow for running the companion backend behind the gateway.

### Changed
- Split gateway upstream targeting into local and container config profiles.
- Expanded the sample LTA DataMall gateway config to cover all companion backend `/api/v1` bus endpoints.
- Documented one-command profile selection and companion integration workflows.

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
- Expanded the sample LTA DataMall gateway config to cover all companion backend `/api/v1` bus endpoints.
- Split gateway upstream targeting into explicit local and container profiles and added a compose workflow for the companion backend.
- Added a companion OpenAPI parity checker and Makefile target to validate gateway route alignment automatically.

### Notes
- The generated API keys file is intentionally gitignored (`config/api_keys.json`).
