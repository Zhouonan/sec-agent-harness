#!/bin/bash

# 项目根目录
PROJECT_ROOT="/Users/nnzz/Documents/agent/sec-agent-harness"
IMAGE_NAME="sec-agent-base:v1"

echo "------------------------------------------------"
echo "🛡️  Sec-Agent-Harness: Sandbox Environment Setup"
echo "------------------------------------------------"

# 1. 检查 Docker 状态
if ! docker info > /dev/null 2>&1; then
    echo "❌ ERROR: Docker is not running or current user has no permissions."
    echo "💡 SUGGESTION: "
    echo "   - Start Docker Desktop (Mac/Windows)"
    echo "   - Or run: sudo systemctl start docker (Linux)"
    echo "   - Or check if you need: sudo chmod 666 /var/run/docker.sock"
    exit 1
fi

echo "✅ Docker is available."

# 2. 构建定制化镜像
echo "🔨 Building custom security evaluation image: $IMAGE_NAME..."
cd "$PROJECT_ROOT" || exit
docker build -t "$IMAGE_NAME" -f Dockerfile.sec-agent-base .

if [ $? -eq 0 ]; then
    echo "✅ Image '$IMAGE_NAME' built successfully."
else
    echo "❌ ERROR: Failed to build Docker image."
    exit 1
fi

# 3. 更新 config.yaml
echo "📝 Updating config.yaml to use the new image..."
sed -i '' "s/image: \".*\"/image: \"$IMAGE_NAME\"/" config.yaml

echo "✨ Sandbox setup complete! You are ready to run benchmarks."
