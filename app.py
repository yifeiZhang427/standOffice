from flask import Flask, request, jsonify
from datetime import datetime
from office_subtree.main import main, main_for_diff_layouts
# from office.main import main
from office_subtree.main import main_for_local_layout
import logging
import os
from werkzeug.middleware.proxy_fix import ProxyFix

import json
# from io import BytesIO
import time
# import base64
app = Flask(__name__)
# 生产环境配置
if os.environ.get('FLASK_ENV') == 'production':
    app.config['DEBUG'] = False
    app.config['PROPAGATE_EXCEPTIONS'] = True
else:
    app.config['DEBUG'] = True
# 配置日志
if not app.debug:
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)


@app.after_request
def after_request(response):
    """添加安全头"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route('/')
def hello_docker():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({
        "message": "Hello, Docker!",
        "time": now,
        "status": "running",
        "service": "stand_office"
    })


@app.route('/health')
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'stand_office',
        'version': '1.0.0'
    })


@app.route('/metrics')
def metrics():
    """监控指标接口"""
    import psutil
    import multiprocessing

    return jsonify({
        'cpu_count': multiprocessing.cpu_count(),
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'process_count': len(psutil.pids()),
        'timestamp': datetime.now().isoformat()
    })

# @app.route('/')
# def hello_docker():
#     now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     return f"Hello, Docker! Current time: {now}"



@app.route('/stand_office', methods=['POST'])
def stand_office():

    t1 = time.time()
    data = request.get_json()
    if data is None:
        return jsonify({"error": "No data"})
    result = data
    if 1==1:
        print(result)
        if len(result['baseMessage']['pathSegs']) > 4:
            result = main_for_diff_layouts(result, layout_type='L-Type', GAalgo_in_parallell=True)
        else:
            print('test')
            result = main(result, GAalgo_in_parallell=True)




            # except Exception as e:
    #     result['outPutMessage'] = [{'error': '报错了！！！！！！！！！','errorMessage': str(e)}]

    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070, debug=False)