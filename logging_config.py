# logging_config.py
import logging
import os


def setup_logging():
    """配置日志系统"""

    # 创建日志目录
    log_dir = "/app/logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 配置日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(),  # 输出到控制台
            logging.FileHandler(f"{log_dir}/app.log")  # 输出到文件
        ]
    )

    # 设置特定库的日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('gunicorn').setLevel(logging.INFO)

    return logging.getLogger(__name__)