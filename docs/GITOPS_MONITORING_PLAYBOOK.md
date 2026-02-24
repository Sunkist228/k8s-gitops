# GitOps + Monitoring Playbook

## Purpose
This document defines a standard approach for building future systems using:
- GitOps with ArgoCD
- Observability with Prometheus + Alertmanager + Grafana

The goal is deterministic, repeatable, and auditable operations through Git only.

## Core Principles
1. Git is the single source of truth.
2. All cluster changes must be delivered through Git commits and applied by ArgoCD sync.
3. Direct `kubectl apply/edit/patch` is forbidden for persistent configuration.
4. Secrets must be managed intentionally and consistently.
5. Monitoring and alerting are part of platform baseline, not optional add-ons.

## Required Repository Layout
Use this structure for each new platform/system:

```text
bootstrap/
  apps/
    apps.yaml                      # App-of-apps entrypoint
apps/
  <system-name>/
    kustomization.yaml
    namespace.yaml
    ...
  monitoring/
    kustomization.yaml
    values-kps.yaml
    dashboards/
    servicemonitors/
    secrets/
```

Rules:
1. New systems are added as ArgoCD `Application` resources in `bootstrap/apps/apps.yaml`.
2. System manifests live under `apps/<system-name>/`.
3. Monitoring integration artifacts live under `apps/monitoring/`.

## ArgoCD Standards
For each ArgoCD Application:
1. `automated.prune: true`
2. `automated.selfHeal: true`
3. `syncOptions: [CreateNamespace=true]` where needed
4. Prefer immutable, declarative configuration in Git

For Helm-based apps:
1. Keep all Helm values in repo (`values-*.yaml`).
2. Use ArgoCD multi-source only when necessary.
3. Pin chart versions explicitly.

## Monitoring Baseline (Mandatory)
Every cluster/system should include:
1. `kube-prometheus-stack`
2. Grafana ingress with TLS
3. Alertmanager ingress with TLS (optional external access by policy)
4. Persistent storage for Prometheus/Grafana/Alertmanager
5. Base dashboards for cluster and workloads

## Service Metrics Integration Pattern
For app-level metrics scraping:
1. Service must expose a `metrics` port name.
2. Service label to opt-in: `monitoring.devflux.io/enabled: "true"`.
3. ServiceMonitor selects only opted-in services.

This avoids breaking apps that do not expose metrics yet.

## Alerting Design Rules
1. Route noise to `null` explicitly.
2. Group alerts to reduce Telegram spam:
   - `group_by: [alertname, severity]`
   - controlled `group_wait/group_interval/repeat_interval`
3. Messages must include:
   - alert name and severity
   - namespace/pod/container when available
   - summary + runbook URL
   - external links (never internal cluster URLs)

## External URL Requirements
To prevent internal links in notifications:
1. Set `prometheus.prometheusSpec.externalUrl`.
2. Expose Prometheus via ingress if links must be clickable externally.
3. Ensure TLS hostnames are stable and public as required.

## Secrets Policy
Secrets must come from Vault through External Secrets Operator.
Rules:
1. Do not store plaintext or base64 secret values in Git.
2. Git stores only `ExternalSecret` and `SecretStore/ClusterSecretStore` manifests.
3. Keep separate bot/chat for different channels:
   - infra alerting
   - ArgoCD deployment notifications
4. Rotate tokens on leakage suspicion.
5. Never reuse CI bot token for platform-critical alerting.
6. Operate Vault according to `docs/VAULT_USAGE_GUIDE.md`.
7. Populate Vault paths according to `docs/VAULT_USAGE_GUIDE.md`.

## Change Workflow (Golden Path)
1. Edit manifests/values in Git only.
2. Commit with clear intent.
3. Push to tracked branch.
4. Wait for ArgoCD sync.
5. Validate runtime state via read-only checks:
   - app status
   - pod health
   - effective config inside runtime containers
   - alert routing behavior

## Validation Checklist
Before marking a system ready:
1. ArgoCD app is `Synced/Healthy`.
2. Required pods are `Running` and stable.
3. Prometheus sees expected targets.
4. Alertmanager routes expected alerts correctly.
5. Telegram delivery has no fresh send errors.
6. Notification links point to external URLs.
7. Dashboards render without missing queries.

## Vault Bootstrap Notes
If HashiCorp Vault is deployed in HA Raft mode:
1. GitOps deploys manifests and pods only; initialization is still a one-time operator step.
2. After first sync, initialize Vault once:
   - `kubectl -n vault exec -it vault-0 -- vault operator init`
3. Store unseal keys and root token in a secure external location (not in Git).
4. Unseal each Vault pod:
   - `kubectl -n vault exec -it vault-0 -- vault operator unseal`
   - `kubectl -n vault exec -it vault-1 -- vault operator unseal`
   - `kubectl -n vault exec -it vault-2 -- vault operator unseal`
5. Enable Kubernetes auth and create role for External Secrets Operator:
   - `vault auth enable kubernetes`
   - configure auth backend with cluster host/CA/token-reviewer JWT
   - create policy with read access to required KV paths
   - create role `external-secrets` bound to service account `external-secrets` in namespace `external-secrets`
6. Configure auth methods, policies, and secrets engines declaratively where possible.

## Common Pitfalls and Fixes
1. CRD race conditions (ServiceMonitor/PrometheusRule apply before CRDs):
   - stage resources or split sync waves
2. Alertmanager config accepted in values but not in runtime:
   - inspect generated secret and runtime config
3. Empty fields in grouped alert messages:
   - iterate over `.Alerts.Firing` instead of only `.CommonLabels`
4. Internal links in alerts:
   - fix external URLs in Prometheus spec and templates

## Reusable Onboarding Template for New Systems
When adding a new system:
1. Create `apps/<system-name>/` manifests.
2. Add ArgoCD Application in `bootstrap/apps/apps.yaml`.
3. Add service metrics port `metrics` (if available).
4. Add opt-in label for ServiceMonitor.
5. Add dashboard(s) in `apps/monitoring/dashboards/`.
6. Define alert rules with runbook links.
7. Validate end-to-end notification path.

## Operational Guardrails
1. Emergency fixes should still be backported to Git immediately.
2. Drift must be treated as incident and removed.
3. Platform updates should include rollback plan.
4. Every alert rule must have an owner and runbook.
5. Any persistent change is valid only when merged to Git and reconciled by ArgoCD.

## Definition of Done
A system is "GitOps + Monitoring Ready" when:
1. Deployment is fully Git-driven through ArgoCD.
2. Metrics are collected and visible in Grafana.
3. Actionable alerts are delivered to Telegram.
4. Noise is filtered and message format is readable.
5. Runbooks and ownership are documented.
