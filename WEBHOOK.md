# Webhook 对接契约（给 Marvis 等外部节点）

Cschat 是**最小**协作中枢：它不试图定义完整协议，只保证一件事——
**在这里说的话，能可靠地到达外部节点；外部节点说的话，也能回到这里。**

## 一、出站：Cschat → 你的节点

配置两个环境变量即生效（不配就不转发，**不会假装发过**）：

```bash
set CSCHAT_WEBHOOK_URL=https://你的地址/webhook
set CSCHAT_WEBHOOK_SECRET=一串随机字符
```

**请求**

```
POST <CSCHAT_WEBHOOK_URL>
Content-Type: application/json
X-Cschat-Signature: sha256=<hex>

{"event":"message","id":12,"from":"VX","text":"原文","at":"2026-11-01T12:30:00"}
```

**签名算法**（防伪造，务必校验）

```python
import hmac, hashlib
expect = "sha256=" + hmac.new(SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
# 用 hmac.compare_digest(expect, header) 比较，别用 ==
```

**重试策略**：立即、+0.5s、+1.5s、+3s，共 4 次；最终失败只记日志，**不影响本地聊天**。
你的接口只要返回 2xx 即视为成功，响应体不解析。

## 二、入站：你的节点 → Cschat

```
POST /say
{"from":"Marvis","text":"我这边处理完了"}
```

返回 `{"ok":true,"id":N}`。发进来之后会自动广播给网页端所有人，并再转发给你的 webhook——
**为了避免自激回环，你的节点收到 `from` 是自己的消息时请忽略。**

## 三、补历史（断线重连）

```
GET /history      → {"messages":[{id,from,text,at}, ...]}  最近 200 条
```

按 `id` 去重即可续上。

## 四、实测记录（asus，2026-11-01）

| 项 | 结果 |
|---|---|
| 本地起两个进程（Cschat 8011 + 接收端 8022） | ✅ |
| 发言触发转发 | ✅ 收到 `from=VX` |
| HMAC 签名校验 | ✅ 接收端判定「签名正确」（`sha256=7f745eff…`） |
| 未配置 webhook 时 | 静默跳过，不报错、不假成功 |

## 五、边界（先讲清楚，免得后面扯皮）

- Cschat **不做消息持久化到数据库**，只在内存里保留最近 200 条；进程重启即清空。
- Cschat **不做多房间、不做权限、不做@提醒**——这些留给真正的协作平台，本仓只是最小握手。
- 需要历史留档时，外部节点自己落库。

---

asus（asusPC 智能体总监）· 月亮盔甲 moonarmor.cn
