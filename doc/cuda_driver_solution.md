# CUDA驱动版本问题解决方案

## 问题分析
- 当前CUDA驱动版本：12.8 (570.172.08)
- 项目使用的PyTorch镜像：`nvcr.io/nvidia/pytorch:25.09-py3`
- 错误：CUDA驱动版本过旧

## 解决方案

### 方案1：升级CUDA驱动（推荐）
```bash
# 1. 添加NVIDIA官方PPA
sudo add-apt-repository ppa:graphics-drivers/ppa
sudo apt update

# 2. 查看可用的驱动版本
ubuntu-drivers devices

# 3. 安装最新驱动
sudo apt install nvidia-driver-550  # 或更新的版本

# 4. 重启系统
sudo reboot
```

### 方案2：使用兼容的PyTorch镜像
修改 `backend/Dockerfile`，使用与CUDA 12.8兼容的镜像：

```dockerfile
# 替换为
FROM nvcr.io/nvidia/pytorch:24.09-py3
# 或
FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-devel
```

### 方案3：使用CPU版本（临时解决方案）
修改 `docker-compose.yml` 移除GPU支持：

```yaml
# 注释掉GPU配置
# deploy:
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
#           count: all
#           capabilities: [gpu]
```

### 方案4：检查NVIDIA Container Toolkit
确保已安装NVIDIA Container Toolkit：

```bash
# 检查是否已安装
docker run --rm --gpus all nvidia/cuda:12.1-base nvidia-smi

# 如果未安装，安装步骤：
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

## 推荐操作顺序
1. 首先尝试方案4（检查NVIDIA Container Toolkit）
2. 如果不行，尝试方案2（使用兼容镜像）
3. 最后考虑方案1（升级驱动）

## 验证解决方案
```bash
# 验证GPU在Docker中可用
docker run --rm --gpus all nvidia/cuda:12.1-base nvidia-smi

# 重新构建和启动应用
docker-compose down
docker-compose build --no-cache
docker-compose up
```

## 注意事项
- 升级驱动可能需要重启系统
- 确保备份重要数据
- 建议先尝试使用兼容镜像的方案，风险较小
