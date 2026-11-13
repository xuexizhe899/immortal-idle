# 部署说明

目标：4h4g 服务器上长期运行，数据落在卷里，重建容器不丢档。

## 0. 当前实际部署方式（2026-11-14）

服务器上已有 Daily-Health 的 nginx 占用 80/443，本游戏复用该入口，**不启用自带 Caddy 的 TLS**：

| 组件 | 位置 | 说明 |
|---|---|---|
| app | `172.17.0.1:18000` → 容器 8000 | 绑 docker0 网关，公网不可达 |
| web | `172.17.0.1:18080` → 容器 80 | Caddy 只跑 HTTP，TLS 由宿主 nginx 终止 |
| 数据 | `app_data` 卷 `/data/xiuxian.db` | 重建容器不丢 |

访问方式：**`http://42.193.116.33`**（服务器 IP）。

域名 `imm.gongye.xin` 已加入宿主 nginx 的 `server_name`，但**腾讯云对 80 端口做了备案拦截**，未备案域名会返回备案提示页，因此当前只用 IP 访问。域名要能用，需在腾讯云备案系统添加该子域名；备案通过后直接在宿主 nginx 加 443 server 块并放入证书即可，容器不用重建。

宿主 nginx 的改动只有一段追加的 server 块，原文件备份在同目录 `nginx-docker.conf.bak-*`。

## 1. 服务器准备（全新机器）

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
