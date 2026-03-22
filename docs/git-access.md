# Git 存取（SSH）

## 原則

- 不將 private key 打進 image。
- 使用 docker-compose volume 掛載 host 端 SSH key。

## compose 掛載

```yaml
volumes:
  - ~/.ssh/id_ed25519:/root/.ssh/id_ed25519:ro
  - ~/.ssh/known_hosts:/root/.ssh/known_hosts:ro
```

## 容器內 SSH config

Dockerfile 會建立 `/root/.ssh/config`：

```sshconfig
Host github.com
  IdentityFile /root/.ssh/id_ed25519
  StrictHostKeyChecking yes
```

## clone 規格

worker 只用 SSH URL：

```bash
git clone git@github.com:org/repo.git
```
