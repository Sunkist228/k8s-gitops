# Backups

Argo CD Application: `backups`

This app owns the Portabase dashboard and in-cluster backup agent for the Playerok dev contour. It deploys into the existing `playerok-dev` namespace so the service names, PVC names, ingress hostnames, and secret references stay stable during the Argo app split.

Required namespace secrets:

- `portabase-app-secret`: `PROJECT_SECRET`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `portabase-credentials`: `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD`
- `database-backup-credentials`: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `portabase-agent-credentials`: `EDGE_KEY`

Keep secret values in Vault/External Secrets. Do not add plaintext or base64 secret payloads to this repository.
