# T12 · 部署、备份与恢复演练

- 里程碑：M4 ｜ 依赖：T11（可提前做服务器准备）｜ 对应文档：DESIGN.md 第 9 节

## 目标
游戏在 4h4g 服务器上长期可访问，且具备真实验证过的备份、恢复与回滚能力。

## 已锁定决策
1. Docker Compose（app + Caddy）；**CI 构建镜像，服务器只 `pull && up`**
2. 本机不装 Docker Desktop；服务器需一次性安装 Docker
3. Caddy 自动签发 HTTPS；`/` 托管前端 dist，`/api/*` 反代到 app:8000
4. SQLite 挂 volume；备份用 `.backup` / `VACUUM INTO`，**禁止裸 `cp` 正在写入的库文件**
5. 回滚 = compose 切回旧 image tag；日志 + 请求追踪，不上 Prometheus

## 要做的事
1. 服务器安装 Docker 与 compose 插件，准备域名与 DNS
2. `deploy/Dockerfile`（后端 + 前端构建产物）、`docker-compose.yml`、`Caddyfile`
3. CI 增加镜像构建与推送；服务器侧一键拉取启动脚本
4. `tools/backup.sh`：定时 `.backup` → 打包 → 留存 30 天；配置 cron
5. `tools/restore.sh`：停服 → 还原 → 起服 → 校验
6. 结构化日志与请求追踪 ID；时钟回拨、CAS 冲突、补算截断记录告警
7. **真实演练**：空服务器重建一次、备份恢复一次、镜像回滚一次

## 产出物
- `deploy/` 全套、备份/恢复脚本、CI 镜像流程、三份演练记录

## 验收
- [ ] HTTPS 可正常访问，证书自动签发与续期
- [ ] 容器重启、服务器重启后存档不丢
- [ ] 空服务器凭仓库 + 一份备份可还原到可玩状态（已演练）
- [ ] 备份恢复成功过一次，恢复后数据完整可玩
- [ ] 切回旧 image tag 可回滚；异常可在日志中定位到 slot 与时间段

## 不做
多环境集群、灰度发布、Prometheus/Grafana、自动扩缩容。

## 注意
"写了备份脚本"不等于完成。本卡的完成标志是**三次演练都有记录**，而不是文件存在。
