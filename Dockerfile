# 使用官方 Playwright Python 镜像（自带 Chromium 浏览器和所有依赖）
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制脚本代码
COPY . .

# 运行脚本
CMD ["python", "LidlConnect.py"]