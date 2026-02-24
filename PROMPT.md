Егор хочет внедрить GitOps. Нужно создать структуру репозитория в E:\local\k8s_gitops на основе манифестов из E:\local\k8s. 
1. Создай папки apps/, bootstrap/, kustomize/. 
2. Перенеси и рефактори манифесты (argocd-ingress, home-assistant, n8n, postgres) из E:\local\k8s в соответствующие папки внутри E:\local\k8s_gitops\apps\. 
3. Используй Kustomize для управления конфигурациями. 
4. Создай App-of-Apps манифесты в bootstrap/ для автоматического развертывания всего кластера через ArgoCD.
5. Напиши README.md с инструкцией по запуску.
