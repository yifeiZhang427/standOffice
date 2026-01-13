# 使用官方 Python 基础镜像
FROM python:3.10

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app
ENV APP_TYPE=mixed
ENV GUNICORN_WORKERS=9
ENV GUNICORN_THREADS=1
ENV GUNICORN_TIMEOUT=3600
ENV GUNICORN_MAX_REQUESTS=500

# 设置 pip 使用清华源加速安装
# 使用阿里云镜像源
RUN echo "deb http://mirrors.aliyun.com/debian/ bullseye main" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bullseye-updates main" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security bullseye-security main" >> /etc/apt/sources.list

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建日志目录（使用 root 权限）
RUN mkdir -p /app/logs/gunicorn && \
    chmod -R 755 /app/logs

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 7070

# 启动命令
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]