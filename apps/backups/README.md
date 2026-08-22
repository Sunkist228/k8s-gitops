# Backups

Argo CD Application: `backups`

This app owns the Portabase dashboard and in-cluster backup agent for the Playerok dev contour. It deploys into the existing `playerok-dev` namespace so the service names, PVC names, ingress hostnames, and secret references stay stable during the Argo app split.

It also adopts the legacy `database-backups` CronJob and its existing PVC. The
CronJob is an independent safety net: Portabase remains the primary scheduler,
while the CronJob creates daily PostgreSQL dumps even if the dashboard is down.

Required namespace secrets:

- `portabase-app-secret`: `PROJECT_SECRET`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `portabase-credentials`: `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD`
- `database-backup-credentials`: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `portabase-agent-credentials`: `EDGE_KEY`

Keep secret values in Vault/External Secrets. Do not add plaintext or base64 secret payloads to this repository.

Optional S3 keys in `database-backup-credentials`:

- `S3_UPLOAD_ENABLED=true`
- `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
- `S3_PROVIDER`, `S3_REGION`, `S3_PREFIX`, `S3_REMOVE_OLDER_THAN_DAYS`

Until those keys are populated in Vault, the CronJob intentionally keeps its
seven-day copy on `database-backup-storage` only. Do not set
`S3_UPLOAD_ENABLED=true` before all required S3 fields exist.

## Recovery checks

After changing database grants or storage credentials:

1. Create a one-off job from the CronJob:
   `kubectl -n playerok-dev create job --from=cronjob/database-backups database-backups-manual-20260823013000`
   (replace the suffix with the current timestamp).
2. Wait for completion and inspect every init-container log. A successful main
   container is not enough if `postgres-backup` failed.
3. Confirm fresh `.sql.gz` files exist on the PVC and, when enabled, under the
   configured S3 prefix.
4. Restore one dump into a disposable database and run a schema/table-count
   smoke test.

The PostgreSQL backup role needs `CONNECT`, schema `USAGE`, and read access to
all current and future tables/sequences. Store that role password in Vault; do
not use a superuser in either backup path.
