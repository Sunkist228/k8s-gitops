# Vault Secrets Bootstrap

## Scope

This runbook fills Vault KV entries used by `ExternalSecret` resources in this repository.

## Prerequisites

1. Vault is initialized and unsealed.
2. You are logged in to Vault with a token that can manage auth, policies, and KV.
3. KV v2 is enabled at path `secret/`.

## Configure Vault for External Secrets Operator

1. Enable Kubernetes auth (once):
  - `vault auth enable kubernetes`
2. Configure Kubernetes auth (replace placeholders):
  - `vault write auth/kubernetes/config kubernetes_host="https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT" kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt token_reviewer_jwt="$TOKEN_REVIEWER_JWT"`
3. Create read-only policy for app secret paths:
  - `vault policy write external-secrets-read - <<EOF`
  - `path "secret/data/monitoring/*" { capabilities = ["read"] }`
  - `path "secret/data/argocd/*" { capabilities = ["read"] }`
  - `path "secret/data/n8n/*" { capabilities = ["read"] }`
  - `path "secret/data/devops-tools/*" { capabilities = ["read"] }`
  - `EOF`
4. Bind role to ESO service account:
  - `vault write auth/kubernetes/role/external-secrets bound_service_account_names=external-secrets bound_service_account_namespaces=external-secrets policies=external-secrets-read ttl=1h`

## Write Secrets to Vault

1. Monitoring Alertmanager:
  - `vault kv put secret/monitoring/alertmanager-telegram telegram-bot-token="<BOT_TOKEN>" telegram-chat-id="<CHAT_ID>"`
2. Monitoring Grafana admin:
  - `vault kv put secret/monitoring/grafana-admin admin-user="<ADMIN_USER>" admin-password="<ADMIN_PASSWORD>"`
3. ArgoCD notifications:
  - `vault kv put secret/argocd/notifications telegram-token="<BOT_TOKEN>" telegram-chat-id="<CHAT_ID>"`
4. n8n:
  - `vault kv put secret/n8n/auth N8N_BASIC_AUTH_PASSWORD="<N8N_PASSWORD>"`
5. jenkins-notify:
  - `vault kv put secret/devops-tools/jenkins-notify telegram-bot-token="<BOT_TOKEN>" telegram-chat-id="<CHAT_ID>" api-keys="<CSV_API_KEYS>"`
6. ingress-manager-api:
  - `vault kv put secret/devops-tools/ingress-manager API_KEY="<API_KEY>" DATABASE_URL="<DATABASE_URL>"`

## Verification

1. `kubectl get externalsecret -A`
2. `kubectl get secret -n monitoring alertmanager-telegram-secret grafana-admin-secret`
3. `kubectl get secret -n argocd argocd-notifications-secret`
4. `kubectl get secret -n n8n n8n-secret`
5. `kubectl get secret -n devops-tools jenkins-notify-secret`
6. `kubectl get secret -n devops-tools ingress-manager-secret ingress-manager-db`

