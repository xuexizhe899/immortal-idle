# 后端运行时镜像：只装运行依赖，启动前执行 alembic 迁移。
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple .

# 放在依赖安装之后：改配置不触发重新装包。
COPY config /config

EXPOSE 8000

# 迁移失败即容器退出，不带着旧表结构对外提供服务。
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
