# OpenClaw GitOps Runbook

## Scope

- OpenClaw is deployed from Git via Argo CD (`apps/openclaw`).
- No Ingress/domain is exposed.
- Access is only through `kubectl port-forward`.
- VPN subscription is stored in Vault and synced by External Secrets Operator.

## Vault Secret

Write VPN subscription URL to Vault:

```bash
vault kv put secret/openclaw/proxy subscription_url="https://example.com/api/v1/client/subscribe?token=..."
```

If you use Vault Web REPL, KV v2 `kv put` is not supported there. Use one of:

1. Vault UI Secrets form:
   - Open mount `secret/`
   - Create secret path `openclaw/proxy`
   - Add key `subscription_url`
2. Vault API explorer from Web REPL:
   - Run `api`
   - Execute `POST /secret/data/{path}` with `path=openclaw/proxy`
   - JSON body:

```json
{
  "data": {
    "subscription_url": "https://example.com/api/v1/client/subscribe?token=..."
  }
}
```

Vault policy reminder for ESO role:

- Grant `read` access to `secret/data/openclaw/*`.
- If using a strict policy file, add path:

```hcl
path "secret/data/openclaw/*" {
  capabilities = ["read"]
}
```

Apply policy from this repo:

```bash
vault policy write external-secrets-read docs/vault-policies/external-secrets-read.hcl
```

Ensure ESO role still uses this policy:

```bash
vault write auth/kubernetes/role/external-secrets bound_service_account_names=external-secrets bound_service_account_namespaces=external-secrets policies=external-secrets-read ttl=1h
```

If `ExternalSecret/openclaw-vpn-subscription` shows `403 permission denied`, force reconcile after policy update:

```bash
kubectl -n openclaw annotate externalsecret openclaw-vpn-subscription force-sync="$(date -Iseconds)" --overwrite
```

## GitOps Sync

1. Commit changes under `apps/openclaw` and `bootstrap/apps/apps.yaml`.
2. Push to repository watched by Argo CD.
3. Wait for `Application/openclaw` to become `Synced` and `Healthy`.

## Access (Port-Forward Only)

Start local tunnel:

```bash
kubectl -n openclaw port-forward deploy/openclaw 18789:18789
```

Open Control UI locally:

```text
http://127.0.0.1:18789/
```

## Gateway Token Retrieval

Gateway token is generated once in the pod and persisted on PVC:

```bash
kubectl -n openclaw exec deploy/openclaw -c openclaw -- cat /home/node/.openclaw/bootstrap/gateway-token
```

## Runtime Contracts

- Vault path: `secret/openclaw/proxy`
- Vault key: `subscription_url`
- Kubernetes Secret: `openclaw-vpn-subscription`
- Kubernetes Secret key: `subscription_url`

## Validation Checklist

1. `ExternalSecret/openclaw-vpn-subscription` is `Ready=True`.
2. Secret `openclaw-vpn-subscription` exists.
3. `proxy-sync` logs show successful fetch and config render from Vault subscription.
4. `/shared/mihomo/config.yaml` is present in pod.
5. `mihomo` listens on internal ports `7890/7891`.
6. `openclaw` health probe succeeds.
7. Port-forwarded UI is reachable at `http://127.0.0.1:18789/`.
