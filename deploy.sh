#!/bin/bash
# deploy.sh — 服务器一键部署脚本
# 适用于 Ubuntu 22.04 腾讯云/阿里云轻量服务器
# 使用方式：chmod +x deploy.sh && ./deploy.sh

set -e

echo "======================================"
echo "  达利欧 AI 投资顾问 — 服务器部署脚本"
echo "======================================"

# ── 1. 安装系统依赖 ────────────────────────────────────────────
echo ""
echo "📦 [1/6] 安装系统依赖..."
apt-get update -q
apt-get install -y -q python3-pip python3-venv nginx certbot python3-certbot-nginx git

# ── 2. 创建 Python 虚拟环境 ────────────────────────────────────
echo ""
echo "🐍 [2/6] 创建 Python 虚拟环境..."
cd /opt
python3 -m venv dalio-env
source dalio-env/bin/activate

# ── 3. 安装 Python 依赖 ────────────────────────────────────────
echo ""
echo "📥 [3/6] 安装 Python 依赖（可能需要几分钟）..."
pip install --upgrade pip -q
pip install fastapi uvicorn[standard] chromadb PyMuPDF \
    langchain langchain-text-splitters sentence-transformers \
    requests python-dotenv pydantic -q

# ── 4. 构建向量索引 ────────────────────────────────────────────
echo ""
echo "📚 [4/6] 构建向量索引..."
echo "⚠️  请确保已将 PDF 书籍放入 /opt/dalio-ai/books/ 目录"
read -p "  books/ 目录已准备好？按 Enter 继续..."

cd /opt/dalio-ai
python ingest.py

# ── 5. 配置 systemd 服务（开机自启）──────────────────────────
echo ""
echo "⚙️  [5/6] 配置系统服务..."
cat > /etc/systemd/system/dalio-api.service << 'EOF'
[Unit]
Description=Dalio AI API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/dalio-ai
Environment=PATH=/opt/dalio-env/bin
ExecStart=/opt/dalio-env/bin/uvicorn api:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable dalio-api
systemctl start dalio-api
echo "  ✅ API 服务已启动"

# ── 6. 配置 Nginx ──────────────────────────────────────────────
echo ""
echo "🌐 [6/6] 配置 Nginx..."
read -p "  请输入你的域名（例如 api.yourdomain.com）：" DOMAIN

cat > /etc/nginx/sites-available/dalio-api << EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/dalio-api /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 申请 SSL 证书（Let's Encrypt 免费）
echo ""
read -p "  是否立即申请 HTTPS 证书？（需要域名已解析到本服务器）[y/N] " SSL
if [[ "$SSL" == "y" || "$SSL" == "Y" ]]; then
    read -p "  请输入你的邮箱（证书到期提醒用）：" EMAIL
    certbot --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive
    echo "  ✅ HTTPS 证书申请成功"
fi

echo ""
echo "======================================"
echo "  🎉 部署完成！"
echo "  API 地址：https://${DOMAIN}"
echo "  健康检查：https://${DOMAIN}/health"
echo "  在小程序 app.js 中将 apiBase 改为上面的地址"
echo "======================================"
