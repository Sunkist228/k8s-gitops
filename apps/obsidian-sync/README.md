# Obsidian Self-hosted LiveSync in GitOps

## Архитектура

Это отдельное GitOps-приложение `apps/obsidian-sync` для Obsidian Self-hosted LiveSync:

- `StatefulSet` с одним replica и отдельным `PersistentVolumeClaim` для `/opt/couchdb/data`;
- `ClusterIP Service`, без `NodePort`;
- внешний доступ только через `Ingress` и TLS-сертификат от существующего `cert-manager` issuer `letsencrypt-prod`;
- `ExternalSecret` подтягивает пароль admin, пользователя Obsidian и AI-пользователей из Vault KV v2 и создает Kubernetes `Secret`;
- `ConfigMap` с CouchDB `local.ini`, включая CORS для Obsidian Desktop и iOS;
- `Job` первичной инициализации создает `_users`, `_replicator`, `_global_changes`, базу `obsidian`, пользователей и read-only guard для AI reader;
- `NetworkPolicy` пускает трафик только от ingress controller и pods с label `obsidian-sync-access=true`;
- `CronJob` делает логический dump CouchDB в отдельный backup PVC.

По умолчанию домен: `notes.devflux.ru`. Namespace: `obsidian-sync`.

В этом репозитории runtime changes доставляются через Argo CD. Не применяйте приложение вручную через `kubectl apply`, кроме аварийной проверки в отдельном кластере.

## Структура файлов

```text
apps/obsidian-sync/
  namespace.yaml
  secret.yaml              # ExternalSecret -> Secret couchdb-credentials
  configmap.yaml
  pvc.yaml
  deployment.yaml
  service.yaml
  ingress.yaml
  networkpolicy.yaml
  init-job.yaml
  backup-cronjob.yaml
  kustomization.yaml
  README.md
```

## Что заменить перед применением

- `notes.devflux.ru` в `ingress.yaml` и `configmap.yaml`: реальный домен CouchDB.
- `ingressClassName: public` в `ingress.yaml`: текущий внешний ingress class этого GitOps repo. Если нужен Traefik или другой nginx class, поменяйте здесь и в `networkpolicy.yaml`.
- `letsencrypt-prod`: имя существующего `ClusterIssuer`. Email Let's Encrypt меняется в манифесте самого issuer, если вы создаете новый issuer отдельно.
- PVC сейчас используют default storage class. Если нужен конкретный `storageClassName`, добавьте его в `pvc.yaml` и `backup-cronjob.yaml`.
- `obsidian-sync`: namespace, если нужен другой. Тогда поменяйте namespace во всех YAML и Argo CD Application.
- Vault path `secret/databases/obsidian-sync`: путь, откуда `ExternalSecret` читает credentials.

## Vault secrets

Секреты не лежат в Git. Запишите их в Vault KV v2:

```bash
vault kv put secret/databases/obsidian-sync \
  COUCHDB_USER="admin" \
  COUCHDB_PASSWORD="<long-random-admin-password>" \
  COUCHDB_SECRET="<long-random-couchdb-secret>" \
  OBSIDIAN_DB="obsidian" \
  OBSIDIAN_USER="obsidian_sync" \
  OBSIDIAN_PASSWORD="<long-random-obsidian-password>" \
  AI_READER_USER="ai_reader" \
  AI_READER_PASSWORD="<long-random-ai-reader-password>" \
  AI_WRITER_USER="ai_writer" \
  AI_WRITER_PASSWORD="<long-random-ai-writer-password>"
```

Для генерации паролей:

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
```

## Доставка через Argo CD

Приложение регистрируется в `bootstrap/apps/apps.yaml` как `Application` `obsidian-sync`. После merge в `main` Argo CD сам применит `apps/obsidian-sync`.

Локальная проверка рендера:

```powershell
kubectl kustomize apps/obsidian-sync
```

Проверка Argo CD:

```powershell
kubectl -n argocd get app obsidian-sync
kubectl -n argocd describe app obsidian-sync
```

Для standalone-теста вне этого GitOps repo можно применить `kubectl apply -k apps/obsidian-sync`, но не используйте этот путь для постоянного cluster state.

## Проверка

```powershell
kubectl -n obsidian-sync get pods,svc,pvc,ingress,job,cronjob
kubectl -n obsidian-sync rollout status statefulset/couchdb
kubectl -n obsidian-sync logs statefulset/couchdb
kubectl -n obsidian-sync logs job/couchdb-init
kubectl -n obsidian-sync get certificate,secret
```

Проверка HTTPS и health:

```powershell
curl.exe -i https://notes.devflux.ru/_up
curl.exe -u "$env:COUCHDB_USER`:$env:COUCHDB_PASSWORD" https://notes.devflux.ru/
curl.exe -u "$env:COUCHDB_USER`:$env:COUCHDB_PASSWORD" https://notes.devflux.ru/_all_dbs
curl.exe -u "$env:OBSIDIAN_USER`:$env:OBSIDIAN_PASSWORD" https://notes.devflux.ru/obsidian
```

Проверка, что сервиса нет через `NodePort`:

```powershell
kubectl -n obsidian-sync get svc couchdb -o jsonpath="{.spec.type}"
```

Ожидаемое значение: `ClusterIP`.

## Настройка Obsidian на Windows

1. В Obsidian откройте нужный vault.
2. Включите Community plugins и установите `Self-hosted LiveSync`.
3. В настройках плагина выберите self-hosted CouchDB.
4. Server URI: `https://notes.devflux.ru`.
5. Database name: `obsidian`.
6. Username: значение `OBSIDIAN_USER`, по умолчанию `obsidian_sync`.
7. Password: значение `OBSIDIAN_PASSWORD`.
8. Включите E2E encryption внутри LiveSync, если храните приватные заметки. Это отдельный пароль плагина, не пароль CouchDB.
9. Запустите начальную синхронизацию и дождитесь завершения.
10. Скопируйте setup URI из LiveSync, чтобы подключить следующие устройства с теми же настройками.

## Настройка Obsidian на iPhone

1. Установите Obsidian и откройте тот же vault или создайте пустой vault.
2. Установите `Self-hosted LiveSync` из Community plugins.
3. Проще всего импортировать setup URI, который создан на первом устройстве.
4. Если настраиваете вручную: Server URI `https://notes.devflux.ru`, database `obsidian`, username/password как у пользователя `obsidian_sync`.
5. Если включали E2E encryption, введите тот же passphrase LiveSync.
6. Дождитесь полной первой синхронизации до редактирования одних и тех же заметок на нескольких устройствах.

## Второе и третье устройство

Для каждого нового устройства используйте setup URI из уже настроенного устройства. Если вводите вручную, используйте ту же базу `obsidian`, тот же CouchDB user `obsidian_sync` и тот же LiveSync E2E passphrase. Не создавайте новую базу для того же vault, иначе устройства будут синхронизироваться в разные места.

## AI API examples

Для AI-агентов не используйте admin. Для чтения `_changes` берите `ai_reader`; для записи через HTTP API берите `ai_writer`. В Kubernetes добавьте внутренним agent pods label:

```yaml
metadata:
  labels:
    obsidian-sync-access: "true"
```

Read-only changes feed:

```powershell
$pair = "$env:AI_READER_USER`:$env:AI_READER_PASSWORD"
curl.exe -u $pair "https://notes.devflux.ru/obsidian/_changes?feed=longpoll&include_docs=true&since=now&timeout=60000"
```

Continuous feed:

```bash
curl -N -u "$AI_READER_USER:$AI_READER_PASSWORD" \
  "https://notes.devflux.ru/obsidian/_changes?feed=continuous&include_docs=true&heartbeat=10000&since=now"
```

Python read example:

```python
import requests

base = "https://notes.devflux.ru"
auth = ("ai_reader", "<AI_READER_PASSWORD>")
params = {"feed": "longpoll", "include_docs": "true", "since": "now", "timeout": 60000}
response = requests.get(f"{base}/obsidian/_changes", auth=auth, params=params, timeout=70)
response.raise_for_status()
for row in response.json().get("results", []):
    print(row["id"], row.get("doc", {}).get("_rev"))
```

Write example for a controlled service:

```bash
curl -u "$AI_WRITER_USER:$AI_WRITER_PASSWORD" \
  -H "Content-Type: application/json" \
  -X PUT "https://notes.devflux.ru/obsidian/agent-note-001" \
  --data '{"type":"agent-note","text":"Created through CouchDB API"}'
```

`ai_reader` включен в members базы, но design document запрещает ему запись. Если нужно еще жестче разделить доступ, создавайте отдельные базы для агентов или выносите запись через backend-сервис с audit log.

## Backup

CronJob `couchdb-backup` каждый день в `03:00 UTC` пишет архивы в PVC `couchdb-backups`.

Запустить backup вручную:

```powershell
kubectl -n obsidian-sync create job --from=cronjob/couchdb-backup couchdb-backup-manual-$(Get-Date -Format yyyyMMddHHmmss)
kubectl -n obsidian-sync get jobs,pods
kubectl -n obsidian-sync logs job/<created-job-name>
```

Посмотреть архивы:

```powershell
kubectl -n obsidian-sync run backup-shell --rm -it --restart=Never `
  --image=docker.io/busybox:1.36.1 `
  --overrides='{"spec":{"securityContext":{"runAsNonRoot":true,"runAsUser":65534,"runAsGroup":65534,"fsGroup":65532,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"backup-shell","image":"docker.io/busybox:1.36.1","command":["sh"],"stdin":true,"tty":true,"securityContext":{"allowPrivilegeEscalation":false,"readOnlyRootFilesystem":true,"runAsNonRoot":true,"runAsUser":65534,"runAsGroup":65534,"capabilities":{"drop":["ALL"]}},"volumeMounts":[{"name":"backups","mountPath":"/backups"}]}],"volumes":[{"name":"backups","persistentVolumeClaim":{"claimName":"couchdb-backups"}}]}}'
```

Внутри shell:

```sh
ls -lh /backups
```

Для критичных заметок одного dump мало: включите snapshot backup на уровне CSI/storage backend и периодически тестируйте restore в отдельный namespace.

## Restore

Безопасный restore делайте в новый namespace или в пустую базу. Не затирайте рабочую базу, пока не проверили результат.

Пример restore job из архива `/backups/couchdb-YYYYMMDDTHHMMSSZ.tar.gz`. Это аварийная операция, а не GitOps-доставка приложения:

```powershell
@'
apiVersion: batch/v1
kind: Job
metadata:
  name: couchdb-restore-manual
  namespace: obsidian-sync
spec:
  backoffLimit: 1
  template:
    metadata:
      labels:
        obsidian-sync-access: "true"
    spec:
      restartPolicy: Never
      securityContext:
        runAsNonRoot: true
        runAsUser: 65532
        runAsGroup: 65532
        fsGroup: 65532
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: restore
          image: docker.io/python:3.12-alpine
          command: ["python", "/scripts/restore.py", "/backups/couchdb-YYYYMMDDTHHMMSSZ.tar.gz"]
          env:
            - name: COUCHDB_URL
              value: http://couchdb:5984
            - name: COUCHDB_USER
              valueFrom:
                secretKeyRef:
                  name: couchdb-credentials
                  key: COUCHDB_USER
            - name: COUCHDB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: couchdb-credentials
                  key: COUCHDB_PASSWORD
          volumeMounts:
            - name: scripts
              mountPath: /scripts
              readOnly: true
            - name: backups
              mountPath: /backups
            - name: tmp
              mountPath: /tmp
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            runAsUser: 65532
            runAsGroup: 65532
            capabilities:
              drop: ["ALL"]
      volumes:
        - name: scripts
          configMap:
            name: couchdb-backup-scripts
            defaultMode: 0555
        - name: backups
          persistentVolumeClaim:
            claimName: couchdb-backups
        - name: tmp
          emptyDir: {}
'@ | kubectl apply -f -
kubectl -n obsidian-sync logs job/couchdb-restore-manual
```

После restore проверьте `_all_dbs`, базу `obsidian`, `_changes`, затем подключите тестовый Obsidian vault.

## Обновление CouchDB без потери данных

1. Сделайте backup и дождитесь его завершения.
2. Прочитайте release notes новой CouchDB версии.
3. Измените image tag в `apps/obsidian-sync/deployment.yaml`, например `docker.io/apache/couchdb:3.5.1` на следующий проверенный patch/minor.
4. Сделайте PR в GitOps repo и дождитесь Argo CD sync.
5. Проверьте rollout:

```powershell
kubectl -n argocd get app obsidian-sync
kubectl -n obsidian-sync rollout status statefulset/couchdb
kubectl -n obsidian-sync exec statefulset/couchdb -- du -sh /opt/couchdb/data
curl.exe -u "$env:COUCHDB_USER`:$env:COUCHDB_PASSWORD" https://notes.devflux.ru/_up
```

Не удаляйте `PVC couchdb-data`. Удаление pod или rollout StatefulSet не удаляет данные, пока PVC остается на месте.

## Security hardening

- Не публикуйте CouchDB через `NodePort` или `LoadBalancer`; только `Ingress` + HTTPS.
- Не используйте admin credentials в Obsidian и AI-агентах.
- Ограничьте доступ к `notes.devflux.ru` по IP на уровне ingress/WAF, если сервис не должен быть публичным.
- Реальные секреты держите в Vault/ESO, SOPS или SealedSecrets.
- Включите NetworkPolicy enforcement в CNI. Без Calico/Cilium/аналогов `NetworkPolicy` не работает.
- Добавьте отдельную базу на каждый vault, если права доступа должны различаться.
- Храните backups на отдельном storage class или выносите их во внешнее object storage.
- Периодически запускайте restore-test в отдельном namespace.
- Если нужен доступ к Fauxton (`/_utils`), давайте его только admin и лучше ограничьте по IP. Obsidian и AI-агентам Fauxton не нужен.

## Troubleshooting

`pod/couchdb` не стартует, initContainer `validate-secrets` падает:

```powershell
kubectl -n obsidian-sync logs statefulset/couchdb -c validate-secrets
```

Почти всегда в Vault нет нужного ключа, `ExternalSecret` еще не синхронизировался или пароль короче 20 символов.

PVC висит в `Pending`:

```powershell
kubectl -n obsidian-sync describe pvc couchdb-data
kubectl get storageclass
```

Добавьте подходящий `storageClassName` в `pvc.yaml` и `backup-cronjob.yaml` или настройте default storage class.

Сертификат не выпускается:

```powershell
kubectl -n obsidian-sync describe certificate
kubectl -n obsidian-sync describe challenge
kubectl describe clusterissuer letsencrypt-prod
kubectl -n obsidian-sync describe ingress couchdb
```

Проверьте DNS `notes.devflux.ru`, ingress class и доступность HTTP-01 challenge снаружи.

Ingress дает 502/504:

```powershell
kubectl -n obsidian-sync get endpoints couchdb
kubectl -n obsidian-sync logs statefulset/couchdb
kubectl -n ingress-nginx logs deploy/ingress-nginx-controller
```

Если используется Traefik, поменяйте `ingressClassName` и проверьте namespace/labels ingress controller в `networkpolicy.yaml`.

Obsidian пишет CORS error:

```powershell
kubectl -n obsidian-sync exec statefulset/couchdb -- cat /opt/couchdb/etc/local.d/obsidian.ini
curl.exe -i -X OPTIONS https://notes.devflux.ru/obsidian `
  -H "Origin: app://obsidian.md" `
  -H "Access-Control-Request-Method: GET"
```

Для iPhone нужен origin `capacitor://localhost`; для Desktop обычно `app://obsidian.md`. Если подключается другой web-клиент, добавьте его origin в `configmap.yaml`.

`couchdb-init` падает с 401:

```powershell
kubectl -n obsidian-sync logs job/couchdb-init
kubectl -n obsidian-sync get secret couchdb-credentials -o yaml
kubectl -n obsidian-sync get externalsecret couchdb-credentials
```

Проверьте `COUCHDB_USER` и `COUCHDB_PASSWORD` в Vault path `secret/databases/obsidian-sync`. После изменения Vault secret форсируйте ESO sync, перезапустите pod и пересоздайте Job:

```powershell
kubectl -n obsidian-sync annotate externalsecret couchdb-credentials force-sync="$(Get-Date -Format s)" --overwrite
kubectl -n obsidian-sync rollout restart statefulset/couchdb
kubectl -n obsidian-sync delete job couchdb-init
```

AI-агент внутри кластера не подключается:

```powershell
kubectl -n <agent-namespace> get pod <agent-pod> --show-labels
kubectl -n obsidian-sync describe networkpolicy couchdb-ingress-only
```

Добавьте agent pod label `obsidian-sync-access=true` или расширьте `networkpolicy.yaml` под конкретный namespace/service account.
