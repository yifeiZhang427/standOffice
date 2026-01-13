#!/bin/bash
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_step() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

# 检查并确定 Docker Compose 命令
determine_compose_cmd() {
    # 先尝试 docker-compose（传统方式）
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
        print_success "使用 docker-compose 命令"
        return 0
    fi

    # 再尝试 docker compose（插件方式）
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
        print_success "使用 docker compose 命令"
        return 0
    fi

    print_error "未找到 docker-compose 命令"
    print_error "请先安装 Docker Compose："
    print_error "1. 传统方式："
    print_error "   curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
    print_error "   chmod +x /usr/local/bin/docker-compose"
    print_error "2. 或使用 Docker 插件（如果已安装 Docker）："
    print_error "   apt-get update && apt-get install docker-compose-plugin"
    exit 1
}

# 检查必需的工具
check_requirements() {
    print_step "检查系统要求..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装"
        echo "安装 Docker："
        echo "curl -fsSL https://get.docker.com | bash"
        exit 1
    fi

    determine_compose_cmd

    print_success "系统检查通过"
}

# 停止旧容器
stop_old_containers() {
    print_step "停止旧容器..."

    if docker ps -a | grep -q "stand-office-app"; then
        docker stop stand-office-app 2>/dev/null || true
        docker rm stand-office-app 2>/dev/null || true
        print_success "旧容器已停止并删除"
    else
        print_success "没有找到旧容器"
    fi
}

# 清理 Docker 资源
clean_docker_resources() {
    print_step "清理 Docker 资源..."

    # 清理已停止的容器
    docker container prune -f 2>/dev/null || true

    # 清理无用的镜像
    docker image prune -f 2>/dev/null || true

    # 清理无用的网络
    docker network prune -f 2>/dev/null || true

    print_success "Docker 资源清理完成"
}

# 构建镜像
build_image() {
    print_step "构建 Docker 镜像..."

    # 清理旧的镜像
    docker image prune -f 2>/dev/null || true

    # 构建新镜像
    if $COMPOSE_CMD build; then
        print_success "镜像构建成功"
    else
        print_error "镜像构建失败"
        exit 1
    fi
}

# 启动容器
start_container() {
    print_step "启动容器..."

    if $COMPOSE_CMD up -d; then
        print_success "容器启动成功"
    else
        print_error "容器启动失败"
        exit 1
    fi
}

# 等待应用就绪
wait_for_app() {
    print_step "等待应用启动..."

    local max_attempts=60
    local attempt=1
    local container_started=false

    while [ $attempt -le $max_attempts ]; do
        # 检查容器是否在运行
        if docker ps | grep -q "stand-office-app"; then
            container_started=true

            # 尝试检查健康状态
            if docker exec stand-office-app wget --quiet --tries=1 --spider http://localhost:7070/health 2>/dev/null; then
                print_success "应用启动成功！"
                return 0
            else
                # 如果容器运行但健康检查失败，立即打印错误
                if [ $attempt -eq 1 ]; then
                    print_error "容器已启动但应用健康检查失败"
                fi

                # 显示启动进度
                echo "健康检查失败，等待重试... ($attempt/$max_attempts)"
            fi
        else
            # 容器未运行，立即打印错误
            if [ "$container_started" = false ] && [ $attempt -eq 1 ]; then
                print_error "容器未启动或已停止"
                echo "正在检查容器状态..."

                # 检查容器是否存在（可能处于停止状态）
                if docker ps -a | grep -q "stand-office-app"; then
                    echo "容器存在但未运行，状态："
                    docker ps -a | grep "stand-office-app"
                    echo ""
                    echo "容器日志（最后10行）："
                    docker logs stand-office-app --tail 10 2>/dev/null || echo "无法获取容器日志"
                else
                    echo "容器不存在"
                fi

                # 不需要继续等待，直接退出
                print_error "应用启动失败"
                echo "查看完整容器日志："
                $COMPOSE_CMD logs --tail=50 2>/dev/null || docker logs stand-office-app --tail 50 2>/dev/null
                exit 1
            fi
        fi

        sleep 2
        ((attempt++))
    done

    if [ "$container_started" = false ]; then
        print_error "容器从未启动成功"
        echo "检查docker-compose配置："
        $COMPOSE_CMD ps
    else
        print_error "应用启动超时（容器已启动但健康检查失败）"
    fi

    echo "查看容器日志："
    $COMPOSE_CMD logs --tail=100 2>/dev/null || docker logs stand-office-app --tail 100 2>/dev/null
    exit 1
}

# 运行健康测试
run_health_tests() {
    print_step "运行健康测试..."

    # 等待一小会儿让应用完全就绪
    sleep 3

    # 测试基本接口
    if curl -s --max-time 5 http://localhost:7070/ > /dev/null; then
        print_success "基础接口正常"
    else
        print_error "基础接口异常"
    fi

    # 测试健康检查接口
    if curl -s --max-time 5 http://localhost:7070/health | grep -q "healthy"; then
        print_success "健康检查接口正常"
    else
        print_error "健康检查接口异常"
    fi
}

# 显示部署信息
show_deployment_info() {
    print_step "部署完成！"

    local ip_address
    ip_address=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")

    echo -e "\n${GREEN}部署信息:${NC}"
    echo -e "应用访问地址: ${YELLOW}http://${ip_address}:7070${NC}"
    echo -e "健康检查地址: ${YELLOW}http://${ip_address}:7070/health${NC}"
    echo -e "超时设置: ${YELLOW}30分钟${NC}"

    echo -e "\n${GREEN}容器状态:${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.RunningFor}}"

    echo -e "\n${GREEN}资源使用:${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" stand-office-app 2>/dev/null || true

    echo -e "\n${GREEN}常用命令:${NC}"
    echo -e "查看实时日志: ${YELLOW}$COMPOSE_CMD logs -f${NC}"
    echo -e "查看应用日志: ${YELLOW}tail -f logs/gunicorn/*.log${NC}"
    echo -e "进入容器: ${YELLOW}docker exec -it stand-office-app bash${NC}"
    echo -e "停止服务: ${YELLOW}$COMPOSE_CMD down${NC}"
    echo -e "重启服务: ${YELLOW}$COMPOSE_CMD restart${NC}"
}

# 主函数
main() {
    echo -e "${GREEN}=== Auto Layout 应用部署脚本 ===${NC}"
    echo -e "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "工作目录: $(pwd)"
    echo -e "超时设置: 30分钟\n"

    # 执行部署步骤
    check_requirements
    stop_old_containers
    clean_docker_resources
    build_image
    start_container
    wait_for_app
    run_health_tests
    show_deployment_info

    echo -e "\n${GREEN}部署脚本执行完成！${NC}"
}

# 执行主函数
main "$@"