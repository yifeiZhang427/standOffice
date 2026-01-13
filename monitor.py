#!/usr/bin/env python3
"""
Auto Layout 应用监控脚本
用法: python monitor.py [--interval 30] [--log-file monitor.log]
"""

import psutil
import time
import subprocess
import json
import argparse
from datetime import datetime
import sys
import requests


class AppMonitor:
    def __init__(self, interval=30, log_file=None):
        self.interval = interval
        self.log_file = log_file
        self.start_time = time.time()

    def get_system_info(self):
        """获取系统信息"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': cpu_percent,
                'cpu_count': psutil.cpu_count(),
                'cpu_per_core': psutil.cpu_percent(percpu=True),
                'memory_total_gb': round(memory.total / (1024 ** 3), 2),
                'memory_used_gb': round(memory.used / (1024 ** 3), 2),
                'memory_percent': memory.percent,
                'disk_total_gb': round(disk.total / (1024 ** 3), 2),
                'disk_used_gb': round(disk.used / (1024 ** 3), 2),
                'disk_percent': disk.percent,
                'load_avg': psutil.getloadavg(),
            }
        except Exception as e:
            return {'error': f'获取系统信息失败: {str(e)}'}

    def get_docker_info(self):
        """获取Docker容器信息"""
        try:
            # 获取容器基本信息
            cmd = ['docker', 'inspect', 'auto-layout-app', '--format',
                   '{{.State.Status}}|{{.State.StartedAt}}|{{.Config.Image}}']
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                status, started_at, image = result.stdout.strip().split('|')

                # 获取资源使用情况
                stats_cmd = ['docker', 'stats', 'auto-layout-app', '--no-stream', '--format', 'json']
                stats_result = subprocess.run(stats_cmd, capture_output=True, text=True)

                stats = {}
                if stats_result.returncode == 0:
                    stats_data = json.loads(stats_result.stdout.strip())
                    stats = {
                        'cpu_percent': stats_data.get('CPUPerc', '0%'),
                        'memory_usage': stats_data.get('MemUsage', '0B'),
                        'memory_percent': stats_data.get('MemPerc', '0%'),
                        'network_io': stats_data.get('NetIO', '0B'),
                    }

                return {
                    'status': status,
                    'started_at': started_at,
                    'image': image,
                    'stats': stats,
                }
        except Exception as e:
            return {'error': f'获取Docker信息失败: {str(e)}'}

        return {'status': 'not_found'}

    def get_gunicorn_info(self):
        """获取Gunicorn进程信息"""
        try:
            # 获取worker数量
            cmd = ['docker', 'exec', 'auto-layout-app', 'ps', 'aux']
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                gunicorn_processes = [line for line in result.stdout.split('\n') if 'gunicorn' in line]
                worker_count = len([p for p in gunicorn_processes if 'worker' in p.lower()])

                # 获取进程详细信息
                processes = []
                for proc in gunicorn_processes[:3]:  # 只取前3个
                    parts = proc.split()
                    if len(parts) >= 11:
                        processes.append({
                            'pid': parts[1],
                            'cpu': parts[2],
                            'mem': parts[3],
                            'command': ' '.join(parts[10:15]),
                        })

                return {
                    'worker_count': worker_count,
                    'total_processes': len(gunicorn_processes),
                    'processes': processes,
                }
        except Exception as e:
            return {'error': f'获取Gunicorn信息失败: {str(e)}'}

        return {'worker_count': 0}

    def test_endpoint(self, endpoint='/health'):
        """测试应用接口"""
        try:
            start_time = time.time()
            response = requests.get(f'http://localhost:7070{endpoint}', timeout=5)
            response_time = (time.time() - start_time) * 1000  # 毫秒

            return {
                'endpoint': endpoint,
                'status_code': response.status_code,
                'response_time_ms': round(response_time, 2),
                'success': response.status_code == 200,
            }
        except requests.exceptions.RequestException as e:
            return {
                'endpoint': endpoint,
                'error': str(e),
                'success': False,
            }

    def get_app_metrics(self):
        """获取应用指标"""
        try:
            response = requests.get('http://localhost:7070/metrics', timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {}

    def collect_all_metrics(self):
        """收集所有监控指标"""
        return {
            'timestamp': datetime.now().isoformat(),
            'system': self.get_system_info(),
            'docker': self.get_docker_info(),
            'gunicorn': self.get_gunicorn_info(),
            'endpoints': {
                'health': self.test_endpoint('/health'),
                'root': self.test_endpoint('/'),
            },
            'app_metrics': self.get_app_metrics(),
            'uptime_seconds': round(time.time() - self.start_time),
        }

    def print_dashboard(self, metrics):
        """打印监控仪表板"""
        print("\n" + "=" * 80)
        print("Auto Layout 应用监控仪表板")
        print("=" * 80)
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"监控间隔: {self.interval}秒")
        print(f"应用运行时间: {metrics['uptime_seconds']}秒")

        # 系统信息
        sys_info = metrics['system']
        if 'error' not in sys_info:
            print("\n[系统资源]")
            print(f"CPU使用率: {sys_info['cpu_percent']:.1f}% ({sys_info['cpu_count']}核)")
            print(
                f"内存使用: {sys_info['memory_used_gb']:.1f}GB / {sys_info['memory_total_gb']:.1f}GB ({sys_info['memory_percent']:.1f}%)")
            print(
                f"磁盘使用: {sys_info['disk_used_gb']:.1f}GB / {sys_info['disk_total_gb']:.1f}GB ({sys_info['disk_percent']:.1f}%)")
            print(
                f"系统负载: {sys_info['load_avg'][0]:.2f}, {sys_info['load_avg'][1]:.2f}, {sys_info['load_avg'][2]:.2f}")

        # Docker信息
        docker_info = metrics['docker']
        if 'error' not in docker_info:
            print("\n[Docker容器]")
            print(f"状态: {docker_info['status']}")
            print(f"镜像: {docker_info['image']}")
            print(f"启动时间: {docker_info['started_at']}")
            if docker_info.get('stats'):
                stats = docker_info['stats']
                print(f"CPU使用: {stats.get('cpu_percent', 'N/A')}")
                print(f"内存使用: {stats.get('memory_usage', 'N/A')}")

        # Gunicorn信息
        gunicorn_info = metrics['gunicorn']
        if 'error' not in gunicorn_info:
            print(f"\n[Gunicorn进程]")
            print(f"Worker数量: {gunicorn_info['worker_count']}")
            print(f"总进程数: {gunicorn_info['total_processes']}")

        # 接口测试
        print("\n[接口健康检查]")
        for endpoint, test in metrics['endpoints'].items():
            status = "✓ 正常" if test.get('success') else "✗ 异常"
            time_ms = test.get('response_time_ms', 0)
            print(f"  {endpoint:10} {status:10} 响应时间: {time_ms:6.2f}ms")

        print("\n" + "=" * 80)

    def save_to_log(self, metrics):
        """保存到日志文件"""
        if self.log_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(metrics) + '\n')
            except Exception as e:
                print(f"写入日志文件失败: {e}")

    def run(self):
        """运行监控"""
        print("开始监控Auto Layout应用... (Ctrl+C 停止)")
        print(f"监控间隔: {self.interval}秒")

        try:
            while True:
                metrics = self.collect_all_metrics()
                self.print_dashboard(metrics)
                self.save_to_log(metrics)

                # 等待下一次监控
                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n监控已停止")
        except Exception as e:
            print(f"监控出错: {e}")


def main():
    parser = argparse.ArgumentParser(description='Auto Layout应用监控脚本')
    parser.add_argument('--interval', type=int, default=30, help='监控间隔(秒)')
    parser.add_argument('--log-file', help='日志文件路径')
    parser.add_argument('--once', action='store_true', help='只运行一次')

    args = parser.parse_args()

    monitor = AppMonitor(interval=args.interval, log_file=args.log_file)

    if args.once:
        metrics = monitor.collect_all_metrics()
        monitor.print_dashboard(metrics)
    else:
        monitor.run()


if __name__ == '__main__':
    main()