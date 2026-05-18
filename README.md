
# Ozon SaaS ERP 全新商业版

## 默认账号
- 管理员：admin
- 密码：admin123456

上线后请立即修改默认密码，或注册新账号后在管理员后台调整权限。

## Railway 部署
Root Directory 设置为：

```text
backend
```

Start Command：

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Variables 必填：

```env
JWT_SECRET=换成一串随机字符串
DOUBAO_API_KEY=ark-你的火山方舟APIKey
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=你的文字模型ep
DOUBAO_IMAGE_MODEL=doubao-seedream-3-0-t2i-250415
```

## Vercel 前端
如果只用 Railway，也可以直接打开 Railway 域名使用，因为后端已经挂载 frontend 静态页面。

如果要前后端分开部署到 Vercel，需要把 frontend 里的 API 地址改成 Railway 后端地址。
