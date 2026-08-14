# Playerok production activation

The production backend and email worker are intentionally committed with zero replicas. Do not scale them up until every item below is complete.

1. Create the production database and a dedicated least-privilege database user.
2. Write every property referenced by `secrets-externalsecret.yaml` to Vault KV path `playerok/playerok`.
3. Apply the `secret/data/playerok/*` rule from `docs/vault-policies/external-secrets-read.hcl` to the Vault policy used by External Secrets Operator.
4. Verify that `playerok-secrets` is `Ready` and contains all expected keys without printing their values.
5. Run the backend Alembic migration job and verify that it succeeds.
6. Test SMTP delivery with `MAIL_DRY_RUN=false` in a controlled rollout.
7. Scale `backend` and `email-worker` to the required replica count through Git and Argo CD.

After the backend is healthy, promote the existing account by running the repository command below in a backend operations pod:

```text
python -m scripts.promote_superadmin korkishkoegor2019
```

The command refuses ambiguous Playerok usernames and does not create an account or password.
