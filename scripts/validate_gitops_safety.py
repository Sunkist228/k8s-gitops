from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]

WORKLOAD_APPS = {
    "backups",
    "home-assistant",
    "n8n",
    "father-testing",
    "ingress-api",
    "playerok-dev",
    "playerok-pre-dev",
    "devflux-artifact-server-dev",
    "devflux-artifact-server",
    "obsidian-sync",
    "jenkins-notify",
    "kv-group",
    "openclaw",
    "omnirouter",
}

AUTOMATED_WORKLOAD_APPS = {
    "backups",
    "playerok-dev",
    "playerok-pre-dev",
}

REQUIRED_SYNC_OPTIONS = {
    "PruneLast=true",
    "ApplyOutOfSyncOnly=true",
    "FailOnSharedResource=true",
}

REQUIRED_KV_GROUP_PDBS = {
    "kv-group-web",
    "kv-group-api",
    "kv-group-mail-web-proxy",
}

MAX_EXTERNAL_SECRET_REFRESH_SECONDS = 300

BACKUPS_PORTABASE_RESOURCES = {
    "portabase.yaml",
}

BACKUPS_PORTABASE_URL = "https://portabase.devflux.ru"
BACKUPS_FORBIDDEN_PORTABASE_URLS = {
    "https://portabase.dev.devflux.ru",
}


def parse_duration_seconds(value: str) -> int | None:
    if not value:
        return None

    unit = value[-1]
    amount = value[:-1]
    if not amount.isdigit():
        return None

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
    }
    multiplier = multipliers.get(unit)
    if multiplier is None:
        return None
    return int(amount) * multiplier


def load_all(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [doc for doc in yaml.safe_load_all(handle) if doc]


def app_name(doc: dict[str, Any]) -> str:
    return str(doc.get("metadata", {}).get("name", ""))


def assert_application_safety() -> list[str]:
    errors: list[str] = []
    docs = load_all(ROOT / "bootstrap" / "apps" / "apps.yaml")
    app_docs = [doc for doc in docs if doc.get("kind") == "Application"]
    bootstrap_app_docs: dict[str, list[Path]] = {}

    for path in (ROOT / "bootstrap" / "apps").glob("*.yaml"):
        for doc in load_all(path):
            if doc.get("kind") != "Application":
                continue
            name = app_name(doc)
            bootstrap_app_docs.setdefault(name, []).append(path.relative_to(ROOT))
            source = doc.get("spec", {}).get("source", {})
            if source.get("repoURL") == "https://github.com/your-username/k8s_gitops.git":
                errors.append(f"{path.relative_to(ROOT)}: placeholder repoURL is still present")

    for name, paths in sorted(bootstrap_app_docs.items()):
        if len(paths) > 1:
            joined = ", ".join(str(path) for path in paths)
            errors.append(f"{name}: duplicate bootstrap Application definitions: {joined}")

    for doc in app_docs:
        name = app_name(doc)
        sync_policy = doc.get("spec", {}).get("syncPolicy", {})
        sync_options = set(sync_policy.get("syncOptions", []) or [])
        missing_options = sorted(REQUIRED_SYNC_OPTIONS - sync_options)
        if missing_options:
            errors.append(f"{name}: missing syncOptions: {', '.join(missing_options)}")

        if name in AUTOMATED_WORKLOAD_APPS:
            automated = sync_policy.get("automated")
            if not isinstance(automated, dict):
                errors.append(f"{name}: automated sync is required")
            else:
                if automated.get("prune") is not True:
                    errors.append(f"{name}: automated.prune must be true")
                if automated.get("selfHeal") is not True:
                    errors.append(f"{name}: automated.selfHeal must be true")
        elif name in WORKLOAD_APPS and "automated" in sync_policy:
            errors.append(f"{name}: workload apps must use manual sync, not automated sync")

    return errors


def assert_kv_group_rollout_safety() -> list[str]:
    errors: list[str] = []
    docs: list[dict[str, Any]] = []
    for path in (ROOT / "apps" / "kv-group").glob("*.yaml"):
        docs.extend(load_all(path))

    deployments = {
        doc.get("metadata", {}).get("name"): doc
        for doc in docs
        if doc.get("kind") == "Deployment"
    }
    pdbs = {
        doc.get("metadata", {}).get("name")
        for doc in docs
        if doc.get("kind") == "PodDisruptionBudget"
    }

    missing_pdbs = sorted(REQUIRED_KV_GROUP_PDBS - pdbs)
    if missing_pdbs:
        errors.append(f"kv-group: missing PodDisruptionBudget resources: {', '.join(missing_pdbs)}")

    for name in sorted(REQUIRED_KV_GROUP_PDBS):
        deployment = deployments.get(name)
        if not deployment:
            errors.append(f"kv-group: missing Deployment/{name}")
            continue

        spec = deployment.get("spec", {})
        strategy = spec.get("strategy", {})
        rolling = strategy.get("rollingUpdate", {})
        if strategy.get("type") != "RollingUpdate":
            errors.append(f"Deployment/{name}: strategy.type must be RollingUpdate")
        if rolling.get("maxUnavailable") != 0:
            errors.append(f"Deployment/{name}: rollingUpdate.maxUnavailable must be 0")
        if rolling.get("maxSurge") != 1:
            errors.append(f"Deployment/{name}: rollingUpdate.maxSurge must be 1")
        if spec.get("minReadySeconds", 0) < 10:
            errors.append(f"Deployment/{name}: minReadySeconds must be at least 10")
        if spec.get("progressDeadlineSeconds", 0) < 120:
            errors.append(f"Deployment/{name}: progressDeadlineSeconds must be at least 120")

        containers = spec.get("template", {}).get("spec", {}).get("containers", [])
        for container in containers:
            cname = container.get("name", "<unnamed>")
            if "startupProbe" not in container:
                errors.append(f"Deployment/{name} container {cname}: missing startupProbe")
            if "readinessProbe" not in container:
                errors.append(f"Deployment/{name} container {cname}: missing readinessProbe")
            if "livenessProbe" not in container:
                errors.append(f"Deployment/{name} container {cname}: missing livenessProbe")

    web = deployments.get("kv-group-web")
    if web and web.get("spec", {}).get("replicas", 0) < 2:
        errors.append("Deployment/kv-group-web: replicas must be at least 2")

    return errors


def assert_external_secret_recovery_safety() -> list[str]:
    errors: list[str] = []

    for path in sorted((ROOT / "apps").rglob("*.yaml")):
        relative_path = path.relative_to(ROOT)
        if "charts" in relative_path.parts or "templates" in relative_path.parts:
            continue

        for doc in load_all(path):
            if doc.get("kind") != "ExternalSecret":
                continue

            refresh_interval = str(doc.get("spec", {}).get("refreshInterval", ""))
            seconds = parse_duration_seconds(refresh_interval)
            name = doc.get("metadata", {}).get("name", "<unnamed>")

            if seconds is None:
                errors.append(
                    f"{relative_path} ExternalSecret/{name}: refreshInterval must use s/m/h duration"
                )
                continue

            if seconds > MAX_EXTERNAL_SECRET_REFRESH_SECONDS:
                errors.append(
                    f"{relative_path} ExternalSecret/{name}: refreshInterval must be <= 5m"
                )

    return errors


def assert_portabase_backups_app_is_isolated() -> list[str]:
    errors: list[str] = []
    app_docs = load_all(ROOT / "bootstrap" / "apps" / "apps.yaml")
    backups_app = next(
        (
            doc
            for doc in app_docs
            if doc.get("kind") == "Application"
            and doc.get("metadata", {}).get("name") == "backups"
        ),
        None,
    )

    if backups_app is None:
        errors.append("backups: missing Argo CD Application registration")
    else:
        spec = backups_app.get("spec", {})
        source = spec.get("source", {})
        destination = spec.get("destination", {})
        if source.get("path") != "apps/backups":
            errors.append("backups: Application source.path must be apps/backups")
        if destination.get("namespace") != "playerok-dev":
            errors.append("backups: Application destination.namespace must be playerok-dev")

    playerok_kustomization = ROOT / "apps" / "playerok-dev" / "kustomization.yaml"
    if "portabase.yaml" in playerok_kustomization.read_text(encoding="utf-8"):
        errors.append("playerok-dev: portabase.yaml must move to apps/backups")

    if (ROOT / "apps" / "playerok-dev" / "portabase.yaml").exists():
        errors.append("playerok-dev: portabase.yaml must not remain under apps/playerok-dev")

    backups_kustomization = ROOT / "apps" / "backups" / "kustomization.yaml"
    if not backups_kustomization.is_file():
        errors.append("backups: missing apps/backups/kustomization.yaml")
    else:
        kustomization = yaml.safe_load(backups_kustomization.read_text(encoding="utf-8")) or {}
        resources = set(kustomization.get("resources", []) or [])
        missing_resources = sorted(BACKUPS_PORTABASE_RESOURCES - resources)
        if missing_resources:
            errors.append(f"backups: missing resources: {', '.join(missing_resources)}")
        if kustomization.get("namespace") != "playerok-dev":
            errors.append("backups: kustomization namespace must be playerok-dev")

    return errors


def assert_portabase_uses_reachable_canonical_url() -> list[str]:
    errors: list[str] = []
    portabase_manifest = ROOT / "apps" / "backups" / "portabase.yaml"
    if not portabase_manifest.is_file():
        return errors

    docs = load_all(portabase_manifest)
    deployment = next(
        (
            doc
            for doc in docs
            if doc.get("kind") == "Deployment"
            and doc.get("metadata", {}).get("name") == "portabase"
        ),
        None,
    )
    if deployment is None:
        errors.append("backups: missing Deployment/portabase")
        return errors

    containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    container = next((item for item in containers if item.get("name") == "portabase"), None)
    if container is None:
        errors.append("backups: missing portabase container")
        return errors

    env = {
        item.get("name"): item.get("value")
        for item in container.get("env", [])
        if "value" in item
    }
    for name in ("PROJECT_URL", "TRUSTED_DOMAINS"):
        if env.get(name) != BACKUPS_PORTABASE_URL:
            errors.append(f"backups: {name} must be {BACKUPS_PORTABASE_URL}")

    manifest_text = portabase_manifest.read_text(encoding="utf-8")
    for forbidden_url in sorted(BACKUPS_FORBIDDEN_PORTABASE_URLS):
        if forbidden_url in manifest_text:
            errors.append(f"backups: forbidden non-resolving URL remains: {forbidden_url}")

    return errors


def main() -> int:
    errors = (
        assert_application_safety()
        + assert_kv_group_rollout_safety()
        + assert_external_secret_recovery_safety()
        + assert_portabase_backups_app_is_isolated()
        + assert_portabase_uses_reachable_canonical_url()
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("GitOps safety checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
