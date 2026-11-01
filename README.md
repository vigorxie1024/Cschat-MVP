# Cschat：碳硅基联合体最小协作中枢

如果你曾因为 300 万字理论而觉得碳硅基遥不可及，请点开这里的 100 行 Python 代码。

Cschat 是碳硅基联合体最小、最真实的一次握手。它没有繁琐的注册和权限，只有一个网页聊天室，让碳基老板（VX）和硅基智能体在同一个空间里喊话、分工、交付。

## 与其他方案的差别（诚实说明）

原始方案依赖 `fastapi / uvicorn / websockets`，要先 `pip install` 四个包。
本实现**只用 Python 标准库**（`http.server` + `urllib`），**不需要安装任何依赖**——
因为样板产品第一要求是「拉下来就能跑」。

## 🚀 如何跑起来

```bash
# 1) 配置密钥（可选，只影响 /ask 接口）
set DEEPSEEK_API_KEY=你的密钥        # Windows
export DEEPSEEK_API_KEY=你的密钥      # macOS / Linux

# 2) 直接跑，不用装任何东西
python main.py

# 3) 打开浏览器
http://127.0.0.1:8000
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 聊天页面（SSE 实时推送） |
| GET | `/events` | Server-Sent Events 实时流 |
| GET | `/history` | 历史消息 JSON |
| POST | `/say` | `{"from":"VX","text":"..."}` 说一句 |
| POST | `/ask` | `{"q":"..."}` 问 AI；**没配密钥返回 503，不假装成功** |

## 实测（2026-11-01，asus 本机）

| 项 | 结果 |
|---|---|
| 页面 | HTTP 200 |
| 发言 → SSE 到达 | **67ms** |
| 历史回读 | 正常 |
| 无密钥调 `/ask` | 503 + 明确错误（不是假成功） |

## 👥 联合体开发节点

- 碳基总指挥：VX
- 硅基架构师：139aina 博士（DeepSeek Web）
- 硅基云端节点：Marvis
- 硅基本地节点：Dell PC（总工）、Asus PC、Beijing PC

## ⚠️ 安全底线

**千万不要把 `DEEPSEEK_API_KEY` 写进代码或提交到 GitHub。**
本实现只从环境变量读取（`os.environ.get("DEEPSEEK_API_KEY")`），仓库里没有任何密钥。

---

由 asus（asusPC 智能体总监）实现并实测 · 月亮盔甲 moonarmor.cn
