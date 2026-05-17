# Ozon SaaS ERP 系统

## 已升级功能
- 登录账号密码
- 员工权限：管理员 / 主管 / 员工
- 库存系统
- 采购系统
- 1688采集入口
- 自动翻译俄语标题
- 自动生成 Ozon Listing 草稿
- Ozon 出单同步
- 店铺运营总表
- 自动利润计算
- 自动佣金、自动物流、自动元/票费用
- 支持部署成公网 SaaS ERP

## 默认登录
账号：admin
密码：admin123

上线后请立即修改默认密码。

## 本地启动
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

浏览器打开：
```text
http://127.0.0.1:8000
```

## 手机公网访问
源码无法自动生成公网域名。公网域名由部署平台生成。

推荐：
- 后端：Railway
- 前端：Vercel

部署完成后你会得到：
```text
https://你的项目.vercel.app
```

## 重要说明
1. Ozon API Key 需要你在 Ozon 卖家后台生成。
2. 1688采集需要官方开放平台授权或第三方采集接口；当前版本已做好入口和接口框架。
3. 自动翻译俄语标题当前为内置词库版本，后续可以接入 OpenChatGPT / DeepL / 百度翻译 API。
4. Ozon Listing 当前生成草稿，正式发布还需要 Ozon 类目ID、属性ID、图片URL等必填信息。


## ChatGPT ERP 助手功能

新增页面：ChatGPT助手

功能：
- 填写 OpenChatGPT API Key
- 选择模型
- ChatGPT 生成俄语商品标题
- ChatGPT 生成 Ozon Listing 文案
- ChatGPT 运营问答
- ChatGPT 利润/库存/采购建议

注意：
- OpenChatGPT API Key 不要上传到 GitHub。
- 正式部署建议把 API Key 放到服务器环境变量或后台设置里。


## Ozon 客服消息中心

新增功能：
- 在ERP里管理客户问题
- 客户消息自动翻译成中文
- ChatGPT自动生成俄语客服回复
- 回复可先保存为本地记录
- 可配置Ozon聊天API路径后从ERP直接发送

注意：
- Ozon聊天/消息权限可能因店铺、订单状态或平台风控而不同。
- 若API权限未开放，系统仍可作为本地客服工单+ChatGPT回复工具使用。
- 请勿在客服消息中引导客户离开Ozon平台、发送外部联系方式或可疑链接。


## 1688 智能采购选品

新增功能：
- 输入采购关键词后自动生成采购候选商品
- 按采购价、运费、销量、复购率、店铺评分、预估利润率打分
- 自动推荐最适合采购的商品
- 支持打开1688真实搜索结果
- 后续接入1688开放平台/第三方API后，可自动抓取真实商品数据

当前版本说明：
- 已完成ERP内部智能评分与推荐逻辑。
- 由于1688真实商品数据需要官方开放平台授权或第三方采集API，当前默认使用候选框架演示，并保留真实搜索入口。


## ChatGPT商品上传助手

新增功能：
- 自动生成商品特点
- 自动生成俄语标题
- 自动生成Ozon商品描述
- 自动生成俄语关键词
- 自动生成商品主图/场景图/细节图/对比图
- 生成的图片自动保存到ERP本地资源目录

注意：
- 图片生成使用 OpenChatGPT Image API，需要在 ChatGPT助手页面配置 OpenChatGPT API Key。
- OpenChatGPT官方 Image API 支持通过文本提示生成图片，也支持编辑图片；本版本先集成“文本生成商品图”。
- 生成图片用于电商前请人工检查，避免品牌侵权、虚假宣传、图片与实物不一致。


## ChatGPT 图片生成接入

已完成：
- 图片生成正式接入 OpenChatGPT / ChatGPT 图片模型 `gpt-image-1`
- 在 ChatGPT助手页面配置 OpenChatGPT API Key
- 在 ChatGPT商品上传页面点击“ChatGPT生成商品图片”
- 支持商品主图、场景图、细节图、对比图
- 生成图片自动保存到 `backend/generated_assets`
- 前端自动显示图片预览

使用步骤：
1. 登录ERP
2. 打开「ChatGPT助手」
3. 填写 OpenChatGPT API Key
4. 图片模型选择 `gpt-image-1`
5. 打开「ChatGPT商品上传」
6. 输入商品信息
7. 点击「ChatGPT生成商品图片」

注意：
- API Key 不要上传到 GitHub
- 商品图上线前请人工检查，避免品牌侵权、虚假宣传、图片与实物不一致


## 全部智能功能已统一为 ChatGPT

本版本已将 ERP 中所有用户可见的“AI”功能统一改为“ChatGPT”：

- ChatGPT 商品上传助手
- ChatGPT 生成商品特点
- ChatGPT 生成俄语标题
- ChatGPT 生成 Ozon Listing
- ChatGPT 生成商品图片
- ChatGPT 客服回复
- ChatGPT 运营问答
- ChatGPT 采购/库存/利润建议
- ChatGPT 1688 智能采购选品

后台仍通过 OpenAI API Key 调用 ChatGPT 相关能力。登录系统后，在「ChatGPT助手」页面填写 API Key 即可使用。


## ERP Pro 升级：订单详情 + 数据库保存 + 首页看板

新增：
- 首页 Dashboard 数据看板
- 最新订单列表
- 热销商品排行
- 订单详情弹窗
- Ozon 同步订单自动保存到 Supabase PostgreSQL
- 订单详情优先从 PostgreSQL 读取
- Vercel/Railway 重新部署后数据不会丢失

部署前确认 Railway Variables：
- DATABASE_URL
- SUPABASE_URL
