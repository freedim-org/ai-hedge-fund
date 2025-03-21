FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装poetry
RUN pip install poetry==1.6.1

# 复制项目文件
COPY pyproject.toml ./
COPY src/ ./src/
COPY .env ./.env
COPY README.md ./README.md

# 配置poetry不创建虚拟环境，直接安装到系统环境
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# 设置环境变量
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8000

WORKDIR /app/src

# 启动命令
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"] 