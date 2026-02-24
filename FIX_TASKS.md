Исправь ошибки в K8s манифестах для GitOps (репозиторий E:\local\k8s_gitops).

Текущие проблемы по логам:
1. **postgres**: init-container `init-postgres-permissions` падает с ошибкой `Read-only file system` при попытке `chmod` на секрет. Я уже пытался это исправить, удалив его, но проверь, что `statefulset.yaml` теперь корректен и использует `emptyDir` для записи сертификатов.
2. **home-assistant**: падает с `PermissionError: [Errno 13] Permission denied: '/config/home-assistant.log'`. Проверь `securityContext` и права на PVC. Возможно, нужно добавить `fsGroup: 1000`.
3. **ingress-api**: висит в `ImagePullBackOff`. Проверь образ в `deployment.yaml`. Там сейчас стоит заглушка `your-repo/ingress-manager-api:latest`. Нужно заменить на реальный образ из Harbor (я видел в логах `harbor.devflux.ru/devops-tools/ingress-manager-api:17`).

После правок сделай git commit и push в репозиторий.
