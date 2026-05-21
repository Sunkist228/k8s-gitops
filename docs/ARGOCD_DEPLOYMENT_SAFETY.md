# Argo CD Deployment Safety

This repository keeps infrastructure controllers on automated sync, but workload
applications use manual sync. A Jenkins or image-tag commit can make an
Application `OutOfSync`, but Argo CD must not push that image into production
until the change is reviewed and synced intentionally.

## Current Guardrails

- Workload Argo CD Applications in `bootstrap/apps/apps.yaml` must not contain
  `spec.syncPolicy.automated`.
- `bootstrap/apps/apps.yaml` is the only App-of-Apps child registry; separate
  duplicate `Application` files under `bootstrap/apps/` are blocked.
- All Applications use `PruneLast=true`, `ApplyOutOfSyncOnly=true`, and
  `FailOnSharedResource=true`.
- `kv-group` web/API/mail proxy rollouts use `RollingUpdate` with
  `maxUnavailable: 0` and `maxSurge: 1`.
- `kv-group-web` runs at least two replicas.
- `kv-group` exposed workloads have startup, readiness, and liveness probes.
- `kv-group` exposed workloads have PodDisruptionBudgets with `minAvailable: 1`.

## Validation

Run this before merging deployment changes:

```powershell
python scripts\validate_gitops_safety.py
kubectl kustomize apps\kv-group
```

The GitHub workflow `.github/workflows/gitops-safety.yml` runs the same safety
check on pull requests and pushes to `main`.

## Promotion Flow

1. CI builds and pushes an immutable image tag.
2. CI or a developer commits the tag change into this GitOps repository.
3. Argo CD shows the workload Application as `OutOfSync`.
4. Review the rendered manifest and smoke-test the image.
5. Sync the Application manually in Argo CD.

If a bad image is committed, revert the Git commit. Do not use `kubectl apply`,
`kubectl edit`, or `kubectl rollout undo` for application state, because Argo CD
will reconcile back to the Git state.
