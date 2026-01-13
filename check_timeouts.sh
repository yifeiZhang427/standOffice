#!/bin/bash
# check_timeouts.sh

echo "=== 检查超时设置 ==="
echo "Gunicorn 超时设置:"
docker exec auto-layout-app cat /app/gunicorn.conf.py | grep "timeout ="

echo -e "\n=== 检查运行时间最长的进程 ==="
docker exec auto-layout-app ps aux --sort=-time | head -10

echo -e "\n=== 检查内存使用 ==="
docker stats --no-stream auto-layout-app

echo -e "\n=== 检查应用健康状态 ==="
curl -s http://localhost:7070/health | python3 -m json.tool

echo -e "\n=== 查看最近错误日志 ==="
docker logs auto-layout-app --tail 20 2>&1 | grep -i "error\|timeout\|killed"