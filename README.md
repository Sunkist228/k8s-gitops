# K8s GitOps Repository

This repository implements the GitOps pattern for managing a Kubernetes cluster using ArgoCD and Kustomize.

## Repository Structure

- `apps/`: Individual application manifests organized by app. Each app uses Kustomize for configuration management.
  - `argocd-ingress/`: Ingress configuration for ArgoCD.
  - `home-assistant/`: Home Assistant deployment.
  - `n8n/`: n8n automation tool deployment.
  - `postgres/`: PostgreSQL StatefulSet and related resources.
  - `vault/`: Vendored HashiCorp Vault Helm chart + local values (HA Raft mode).
- `bootstrap/`: ArgoCD "App-of-Apps" manifests for cluster initialization.
  - `root-app.yaml`: The main application that watches the `bootstrap/apps/` folder.
  - `apps/apps.yaml`: Definitions for all applications in the cluster.
- `kustomize/`: Shared Kustomize bases and components.

## How to Initialize

1. **Install ArgoCD** (if not already installed):
   ```bash
   kubectl create namespace argocd
   kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   ```

2. **Apply the Root Application**:
   Edit `bootstrap/root-app.yaml` and `bootstrap/apps/apps.yaml` to replace the `repoURL` placeholder (`https://github.com/your-username/k8s_gitops.git`) with your actual repository URL.

   Then apply the root application:
   ```bash
   kubectl apply -f bootstrap/root-app.yaml
   ```

3. **ArgoCD will automatically**:
   - Create a sub-application for each app defined in `bootstrap/apps/apps.yaml`.
   - Deploy the resources from `apps/<app-name>` into the cluster.
   - Synchronize any changes made to this repository.

## Refactoring Notes

The original manifests from `E:\local\k8s` were refactored into Kustomize-friendly structures:
- Monolithic YAML files were split into smaller logical components (Deployment, Service, PVC, etc.).
- Namespaces are managed via Kustomize or ArgoCD `syncOptions` (`CreateNamespace=true`).
- Sensitive data like Secrets should be further managed using tools like Sealed Secrets or External Secrets.

## Ingress API Delivery Flow

`ingress-api` is deployed from `apps/ingress-api` by ArgoCD App-of-Apps (`bootstrap/apps/apps.yaml`).

Pipeline contract:
- Jenkins builds and pushes image to Harbor.
- Jenkins commits only the image tag change in `apps/ingress-api/deployment.yaml`.
- ArgoCD auto-sync (`prune + selfHeal`) applies the new revision.

Runtime startup hardening is configured via `apps/ingress-api/config.yaml`:
- `DB_STARTUP_MAX_ATTEMPTS`
- `DB_STARTUP_RETRY_DELAY_SECONDS`
- `DB_STARTUP_FAIL_FAST`
