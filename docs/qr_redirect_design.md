# 动态二维码重定向服务设计文档

## 1. 需求概述

### 1.1 业务场景

实现一个线下活动用的动态二维码重定向服务，用于 Blued App 扫码后的安全跳转验证。

### 1.2 核心需求

- iPad 展示的二维码内容固定为：`https://activity.bluedhealth.com/weal/shnyu/redirect?token=<token>`
- 参与者必须用 Blued App 在二维码 30 秒有效期内扫码
- Blued 侧在扫码后重定向到我们域名：`https://shnyu.danlanlove.com?token=<token>&key=<uuid>&...`
- 支持同一 token 在有效期内多人并发使用
- 前端每 25-28 秒自动生成新的 JWT token 并刷新二维码
- 不影响现有的直接跳转方式

## 2. 架构设计

### 2.1 系统架构

```
┌─────────────────────────────────────────┐
│   iPad 展示页面（独立前端页面）            │
│                                          │
│  每 25-28 秒：                            │
│  前端使用共享密钥生成 JWT token           │
│  (payload: {iat, exp=iat+30s})          │
│                                          │
│  生成二维码 URL：                         │
│  https://activity.bluedhealth.com/       │
│  weal/shnyu/redirect?token=<token>       │
│                                          │
│  显示二维码供用户扫描                      │
└──────────────────────────────────────────┘
            │
            │ 用户用 Blued App 扫码
            ▼
┌──────────────────────────────────────┐
│  https://activity.bluedhealth.com    │
│  /weal/shnyu/redirect?token=<token>  │ 
└──────────────────────────────────────┘
            │
            │ Blued 侧重定向
            ▼
┌──────────────────────────────────────────┐
│  https://shnyu.danlanlove.com            │
│  ?token=<token>&key=<uuid>&...           │
│                                          │
│  1. Blued 侧重定向到前端根路径            │
│     (pages/index.js 接收到 query 参数)    │
│                                          │
│  2. 前端 pages/index.js 主动调用:         │
│     GET /api/key?token=...&key=...       │
│                                          │
│  3. 后端 key view 处理:                   │
│     - 验签 JWT token                      │
│     - 检查 exp 是否过期                    │
│     - 验证 key                            │
│                                          │
│  4. 响应:                                 │
│     - 200 OK: 验证通过，前端继续流程       │
│     - 419 Token Expired: JWT 失效，        │
│         前端跳转到失效页                   │
│     - 404 Not Found: key 无效，           │
│         前端跳转到 qualtrics              │
└──────────────────────────────────────────┘
```

### 2.2 技术栈

- **后端框架**: Django + Django REST Framework
- **JWT 库**:
  - 后端：PyJWT (HMAC-SHA256)
  - 前端：jsonwebtoken (HMAC-SHA256)
- **密钥管理**: 前后端共享固定密钥（存储在环境变量/配置中）

## 3. 接口设计

### 3.1 GET /api/key

前端 `pages/index.js` 调用的验证接口，用于验证来自 Blued 重定向的 token 和 key。

**调用流程**

1. Blued 侧重定向到前端：`https://shnyu.danlanlove.com?token=<token>&key=<uuid>&...`
2. 前端 `pages/index.js` 接收到 query 参数（通过 `router.query`）
3. 前端主动调用后端：`GET /api/key?token=...&key=...`
4. 后端验证并返回结果
5. 前端根据返回结果继续处理（继续流程、跳转失效页或跳转 qualtrics）

**请求**

```
GET /api/key?token=<jwt_token>&key=<uuid>&...
```

**Query 参数**

- `token`: JWT token，由前端从 URL query 参数中获取并传递（来自 Blued 侧透传）
- `key`: UUID，由前端从 URL query 参数中获取并传递（来自 Blued 侧追加）

**处理逻辑**

1. **有 token 的情况**（新流程）

   - 先验证 JWT 签名（HMAC-SHA256）
   - 检查 `exp` 字段是否过期（允许 3-5 秒时钟偏差）
   - JWT 验证通过后，继续验证 `key` 参数（检查 Screen 表中是否存在）
   - 都通过：返回 `200 OK`，前端继续正常业务流程
   - JWT 验证失败：返回 `419 Token Expired`，前端跳转到失效页
   - Key 验证失败：返回 `404 Not Found`（原有逻辑）
2. **无 token 的情况**（旧流程）

   - 直接走原有的 key 验证逻辑
   - 如果 `key` 存在且在 Screen 表中，返回 `200 OK`
   - 否则返回 `404 Not Found`
   - 前端根据返回状态继续原有流程（如验证后跳转到 qualtrics 或登录）

**错误响应**

- `419 Token Expired`: JWT token 验证失败（过期或签名错误），前端应跳转到失效页面
- `404 Not Found`: key 参数无效或不存在
