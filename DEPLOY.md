# Docker 部署指南

本文档提供了如何使用 Docker 部署 AI Hedge Fund 项目的详细说明。

## 前提条件

确保服务器上已安装以下软件：

- Docker (20.10.0 或更高版本)
- Docker Compose (2.0.0 或更高版本)

## 部署步骤

### 1. 准备环境变量

在项目根目录下，确保有一个 `.env` 文件包含所有必要的环境变量。您可以基于 `.env.example` 创建：

```bash
cp .env.example .env
```

然后编辑 `.env` 文件，填入必要的配置，如 API 密钥等。

### 2. 使用 Docker Compose 构建并启动服务

在项目根目录下执行以下命令：

```bash
# 构建并启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

服务将在后台运行，并绑定到主机的 8000 端口。您可以通过浏览器访问 `http://您的服务器IP:8000/docs` 查看 API 文档。

### 3. 停止服务

如需停止服务，执行以下命令：

```bash
docker-compose down
```

## 手动构建与运行 (不使用 Docker Compose)

如果您希望手动构建和运行 Docker 镜像，可以执行以下命令：

```bash
# 构建 Docker 镜像
docker build -t ai-hedge-fund .

# 运行容器
docker run -d --name ai-hedge-fund -p 8000:8000 --env-file .env ai-hedge-fund
```

## 生产环境配置建议

对于生产环境，建议做以下调整：

1. 在 Dockerfile 中使用多阶段构建，减小最终镜像大小
2. 配置 HTTPS，可以通过 Nginx 或 Traefik 等反向代理实现
3. 设置适当的 CORS 策略，限制允许访问的域名
4. 实现适当的日志管理方案
5. 考虑使用 Docker Swarm 或 Kubernetes 进行容器编排，以实现高可用性

## 故障排除

如果遇到问题，可以尝试以下步骤：

1. 检查容器日志：`docker-compose logs` 或 `docker logs ai-hedge-fund`
2. 确保所有必要的环境变量已正确设置
3. 确保服务器防火墙已开放 8000 端口 