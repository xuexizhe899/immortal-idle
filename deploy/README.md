# 部署说明

目标：4h4g 服务器上长期运行，数据落在卷里，重建容器不丢档。

## 1. 服务器准备（首次）

```bash
# 安装 Docker 与 compose 插件（Debian/Ubuntu）
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker compose version
```

域名 A 记录指向服务器公网 IP，等生效后再启动，否则 Caddy 申请证书会失败。

## 2. 首次部署

```bash
git clone <仓库地址> /opt/immortal-idle
cd /opt/immortal-idle/deploy
cp env.example .env
# 编辑 .env，填入 SITE_ADDRESS 与 TAG
docker compose up -d --build
docker compose logs -f web   # 看到 certificate obtained 即成功
```

首次构建会拉 Node 与 Python 镜像，4h4g 上大约 3–6 分钟。若 `npm ci` 因内存被杀，先在本地构建并推送镜像，再改成 `image:` 引用。

## 3. 更新

```bash
cd /opt/immortal-idle && git pull
cd deploy && docker compose up -d --build
```

数据库迁移在容器启动时自动执行（`alembic upgrade head`），失败则容器退出，不会带旧表结构运行。

## 4. 回滚

```bash
# .env 里把 TAG 改成上一个版本
docker compose up -d
```

镜像按 tag 保留，回滚不重建。schema 降级需单独执行 `alembic downgrade`，不要与回滚混在一起。

## 5. 数据

- 存档数据库在 `app_data` 卷的 `/data/xiuxian.db`。
- 备份与恢复脚本、定时任务属于 T12 剩余部分，尚未提供。**在此之前请手动备份**：

```bash
docker compose exec app sh -c 'sqlite3 /data/xiuxian.db ".backup /data/backup.db"'
docker cp $(docker compose ps -q app):/data/backup.db ./backup-$(date +%F).db
```

不要直接 `cp` 正在写入的数据库文件。

## 6. 注意

- `.env` 不进 Git。
- `deploy/` 下的文件修改后需要 `docker compose up -d --build` 才生效。
- 日志走容器 stdout，`docker compose logs` 查看；未接入集中收集。
