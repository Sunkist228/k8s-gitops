# Backups

Argo CD Application: `backups`

This app adopts the legacy `database-backups` CronJob and its existing PVC in
the `playerok-dev` namespace. The CronJob is an independent safety net:
Portabase remains the primary scheduler, while the CronJob creates daily
PostgreSQL dumps even if the dashboard is down.

Portabase itself intentionally remains owned by `Application/playerok-dev`.
Moving its deployments and PVCs between two auto-sync applications needs a
separate two-phase ownership transfer; doing that in the same revision risks
the old application pruning persistent resources before the new application
adopts them.

Required namespace secret:

- `database-backup-credentials`: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

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
