# Playerok production activation

This directory is an inactive production scaffold. The backend and email worker intentionally have zero replicas, and `bootstrap/apps/apps.yaml` intentionally has no `playerok` Argo CD Application. Merging manifest updates must not activate production by accident.

## Verified starting point (2026-08-14)

- PostgreSQL already contains an empty `playerok_prod` database. It is still owned by the shared `playerok` role and needs a dedicated least-privilege login before activation.
- `api.devflux.ru` and `playerok-devflux.devflux.ru` resolve to `77.39.8.68`.
- `devflux.ru` and `www.devflux.ru` do not yet resolve.
- External Secrets Operator and the `vault-backend` ClusterSecretStore are ready. The contents of Vault KV `playerok/playerok` have not been verified.
- The proven SMTP transport is Yandex Postbox over port 587 with STARTTLS. Keep `MAIL_DRY_RUN=true` until a controlled production delivery succeeds.
- The `playerok` namespace is not allowed to reach PostgreSQL until the companion `devflux-artifact-network` policy change is synced.

## Preflight

1. Create a dedicated `playerok_prod` PostgreSQL login with a generated password, transfer ownership of the empty `playerok_prod` database to it, and grant only the required database/schema privileges.
2. Write every property referenced by `secrets-externalsecret.yaml` to Vault KV `playerok/playerok`, including `HARBOR_DOCKERCONFIGJSON`. Do not copy development JWT, TOTP, database, or SMTP credentials into production.
3. Apply the `secret/data/playerok/*` rule from `docs/vault-policies/external-secrets-read.hcl` to the Vault policy used by External Secrets Operator.
4. Sync `devflux-artifact-network`, then verify TCP connectivity from a disposable pod in `playerok` to `postgres-service.databases.svc.cluster.local:5432`.
5. Add DNS records: apex `A 77.39.8.68`, `www CNAME devflux.ru.`, and update BIMI to `https://devflux.ru/bimi.svg`. Keep the legacy hostname during rollout.
6. Verify `playerok-secrets` and `harbor-registry` are `Ready` and contain all expected keys without printing values.
7. Build and push immutable production frontend/backend images from the approved application release.

## Activation

1. Add the `playerok` Argo CD Application in a separate, explicitly approved commit with automated prune/self-heal and `CreateNamespace=true`.
2. Sync with backend and email worker still at zero replicas. Verify frontend ingress, TLS for all three hosts, image pull, probes, and public static assets.
3. Run the backend Alembic migration job against `playerok_prod` and verify the current revision.
4. Scale backend to one replica through Git. Verify `/health`, `/metrics`, the public pricing endpoint, and a beta application written to the production database.
5. Send one controlled SMTP test, verify the outbox record becomes `sent`, then change `MAIL_DRY_RUN=false` through Git.
6. Scale email worker to one replica through Git. Verify its heartbeat, metrics, and alerts.
7. Promote the existing owner account, test the admin beta queue and a disposable invitation from request through registration, then remove the disposable records.
8. Check `devflux.ru`, `www.devflux.ru`, `api.devflux.ru`, and the legacy hostname externally before enabling announcements.

Rollback by reverting the activation/image commit in GitOps and syncing Argo CD. Do not delete the database or Vault values during rollback.

After the backend is healthy, promote the existing account by running the repository command below in a backend operations pod:

```text
python -m scripts.promote_superadmin korkishkoegor2019
```

The command refuses ambiguous Playerok usernames and does not create an account or password.
