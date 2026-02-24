# GitOps Rule

- All runtime Kubernetes changes must be delivered through this Git repository and reconciled by Argo CD.
- Do not use `kubectl apply`, `kubectl edit`, or manual in-cluster mutations for application changes.
- Allowed manual action: initial Argo CD bootstrap (`bootstrap/root-app.yaml`) and read-only diagnostics.
- Any new app must include:
  - manifests under `apps/<app-name>/` (Kustomize-friendly layout),
  - registration in `bootstrap/apps/apps.yaml` as an Argo CD `Application`.
