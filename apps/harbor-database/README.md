# PostgreSQL Harbor

Argo CD управляет существующим `StatefulSet/harbor-database` в `devops-tools`.
Остальные компоненты Harbor остаются в Helm-релизе `harbor` версии `1.17.2`.
После изменения Helm-релиза проверяйте согласованность его настроек базы с этим
каталогом: Helm не должен возвращать старые проверки здоровья.

## Причина изменения

В журналах 2 октября 2026 года в 01:38:47 и 01:43:59 по Москве тайм-аут
`ExecSync` контейнера PostgreSQL совпал с завершением процесса базы с кодом 141.
После этого PostgreSQL прерывал соединения и запускал восстановление. Harbor
возвращал `UNAUTHORIZED` с вложенной ошибкой `SQLSTATE 57P03`, что срывало
загрузку слоёв образов в Jenkins.

Старая проверка `/docker-healthcheck.sh` выполняла `SELECT 1` через Bash и `psql`;
Kubernetes обрывал её через одну секунду. Новые проверки используют
[`pg_isready`](https://www.postgresql.org/docs/15/app-pg-isready.html): внутренний
тайм-аут подключения — 3 секунды, внешний тайм-аут Kubernetes — 10 секунд.
Startup probe даёт базе до 10 минут на запуск и восстановление. Liveness probe
допускает минуту ошибок, readiness probe убирает неготовую базу из сервиса.

Базе выделены запросы `250m` CPU и `256Mi` памяти. Память ограничена `2Gi`;
лимит CPU не задан, чтобы не замедлять восстановление при свободном CPU узла.
Перед остановкой `SIGINT` запускает штатное быстрое завершение PostgreSQL:
текущие транзакции откатываются, база сохраняет данные и закрывает соединения.

## Применение и проверка

Приложение `harbor-database` синхронизируется вручную. Изменение вызывает
короткий перезапуск базы. Образ `goharbor/harbor-db:v2.13.2`, имя StatefulSet,
селекторы, Secret, PGDATA и шаблон PVC сохранены из действующей установки.
`Prune=false,Delete=false` и политика `Retain` защищают StatefulSet и данные
от удаления вместе с приложением Argo CD.

Перед синхронизацией сохраните закрытую резервную копию `registry` через
`pg_dump -Fc`, проверьте серверный dry-run и отсутствие изменений хранилища.
После синхронизации проверьте `Synced/Healthy`, SQL-запрос, API здоровья Harbor,
аутентификацию реестра и загрузку существующего образа. При откате используйте
обратный Git-коммит и синхронизацию Argo CD.

```powershell
python scripts/validate_gitops_safety.py
kubectl kustomize apps/harbor-database
kubectl -n devops-tools rollout status statefulset/harbor-database
kubectl -n devops-tools exec harbor-database-0 -c database -- psql -U postgres -d registry -c "SELECT 1"
```
