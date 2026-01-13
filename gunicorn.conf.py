import multiprocessing
import os
import math

# 绑定地址和端口
bind = "0.0.0.0:7070"


def get_available_cpus():
    """获取可用的 CPU 核心数"""
    try:
        # 读取容器 CPU 限制（如果设置了）
        cfs_quota = "/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_quota_us"
        cfs_period = "/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_period_us"

        if os.path.exists(cfs_quota) and os.path.exists(cfs_period):
            with open(cfs_quota) as f:
                quota = int(f.read().strip())
            with open(cfs_period) as f:
                period = int(f.read().strip())

            if quota > 0 and period > 0:
                cpus = math.ceil(quota / period)
                if cpus > 0:
                    return cpus
    except:
        pass

    # 回退到系统 CPU 核心数
    try:
        return multiprocessing.cpu_count()
    except:
        return 1


# 获取 CPU 核心数并计算 workers
available_cpus = get_available_cpus()
print(f"[Gunicorn] 检测到 CPU 核心数: {available_cpus}")

# 根据应用类型调整 worker 数量
app_type = os.getenv('APP_TYPE', 'mixed').lower()
env_workers = os.getenv('GUNICORN_WORKERS')

if env_workers:
    # 优先使用环境变量设置
    workers = int(env_workers)
else:
    # 根据 CPU 核心数自动计算
    if app_type == 'io':
        workers = available_cpus * 2 + 1  # I/O 密集型
    elif app_type == 'cpu':
        workers = available_cpus + 1  # CPU 密集型
    else:
        workers = int(available_cpus * 1.5)  # 混合型

# 设置限制
max_workers = int(os.getenv('GUNICORN_MAX_WORKERS', '40'))
min_workers = int(os.getenv('GUNICORN_MIN_WORKERS', '4'))
workers = max(min(workers, max_workers), min_workers)

print(f"[Gunicorn] 最终设置 workers 数量: {workers}")

# 线程数
threads = int(os.getenv('GUNICORN_THREADS', '2'))

# Worker 类型
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')

# 日志配置 - 输出到标准输出和文件
accesslog = "-"
errorlog = "-"
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')

# 进程名称
proc_name = "auto_layout_app"

# 内存管理 - 定期重启 worker 防止内存泄漏
max_requests = int(os.getenv('GUNICORN_MAX_REQUESTS', '500'))
max_requests_jitter = int(os.getenv('GUNICORN_MAX_REQUESTS_JITTER', '50'))

# 超时设置 - 设置为 30 分钟（1800秒）
timeout = int(os.getenv('GUNICORN_TIMEOUT', '3600'))
print(f"[Gunicorn] 超时时间设置为: {timeout} 秒 ({timeout / 60} 分钟)")

# 连接保持
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '5'))

# 预热应用（加快 worker 启动）
preload_app = os.getenv('GUNICORN_PRELOAD', 'False').lower() == 'true'

# 优雅关闭
graceful_timeout = int(os.getenv('GUNICORN_GRACEFUL_TIMEOUT', '60'))

# 守护进程模式（在 Docker 中设置为 False）
daemon = False

# 设置环境变量
raw_env = [
    'FLASK_DEBUG=0',
    'FLASK_ENV=production',
    'PYTHONPATH=/app',
    f'GUNICORN_WORKERS={workers}',
]