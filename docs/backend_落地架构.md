# 医疗导航 Agent 后端落地架构（Python + FastAPI + LangChain）

## 1. 总体架构
后端为双 Agent + 多服务技能：
1. GPT Triage Agent（OpenAI）
   - 负责分诊、置信度、follow-up 问题生成。
2. Gemini Navigation Agent（Google）
   - 负责机构检索提示和保险说明补充。
3. Skills
   - Google Maps Places：附近机构搜索
   - Tavily Search：症状到科室的参考检索（供 GPT 分诊上下文）
   - Follow-up Memory：去重已问症状
   - Geocode Service：位置文本转经纬度

## 2. 核心分诊规则
1. 置信度门槛：`confidence_percent > 80` 才进入 `TRIAGE_READY`。
2. 低置信度进入 `FOLLOW_UP`，每轮固定 4 条第一人称陈述句症状。
3. follow-up 候选症状去重：基于 `/tmp/healthcare_guidance_asked_symptoms.json`。
4. 推荐响应新增字段：
   - `visit_needed: bool`
   - 用于区分“需要就医”与“可先自我护理”。

## 3. 状态机
主状态：
`PROFILE(前端) -> INTAKE -> FOLLOW_UP -> TRIAGE_READY -> PROVIDER_MATCHED -> INSURANCE -> INSURANCE_RESULT -> BOOKING -> COMPLETED`

分支：
- `ESCALATED`：红旗症状分支。
- `TRIAGE_READY` 且 `department=Primary Care && care_path=PRIMARY_CARE && visit_needed=false`：
  前端不进入 provider 流程，直接回首页或重写症状。

## 4. API 契约（当前实现）

### 4.1 地理解析
- `POST /api/v1/geo/geocode`
- 请求：`{ "query": "..." }`
- 响应：`query, normalized_address, lat, lng, source`
- 失败行为：返回 `422`（前端会转 GPS 定位兜底）

### 4.2 分诊会话
- `POST /api/v1/triage/sessions`
- 返回：`status, confidence_percent, questions[]`

### 4.3 提交 follow-up
- `POST /api/v1/triage/sessions/{session_id}/answers`

### 4.4 获取推荐
- `GET /api/v1/triage/sessions/{session_id}/recommendation`
- 关键字段：
  - `department`
  - `care_path`
  - `confidence_percent`
  - `visit_needed`
  - `reasons`
  - `red_flags_detected`

### 4.5 推荐反馈
- `POST /api/v1/triage/sessions/{session_id}/recommendation-feedback`
- `AGREE -> PROVIDER_MATCHED`
- `DISAGREE -> FOLLOW_UP`

### 4.6 机构/保险/预约
- `POST /api/v1/providers/search`
- `POST /api/v1/insurance/check`
- `POST /api/v1/booking/intents`
- `GET /api/v1/triage/sessions/{session_id}/summary`

## 5. 模型与配置
`.env` 关键项：
- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `GEMINI_API_KEY`, `GEMINI_MODEL`
- `GOOGLE_MAPS_API_KEY`
- `TAVILY_API_KEY`

## 6. Per-Request API Key Override（2026-04-17 新增）

### 6.1 机制概述
前端可通过自定义请求头传入 API Key，后端优先使用该 Key，无传入则回退到 `.env` 默认值。

### 6.2 新增文件
- `app/core/request_context.py`：四个 `ContextVar`（`openai_key_override` / `google_maps_key_override` / `gemini_key_override` / `tavily_key_override`）。

### 6.3 中间件（`app/main.py`）
```python
@app.middleware('http')
async def extract_api_keys(request, call_next):
    openai_key_override.set(request.headers.get('X-OpenAI-Key', ''))
    # ... 同理 Google Maps / Gemini / Tavily
    return await call_next(request)
```

### 6.4 Helper 函数（`app/core/config.py`）
- `get_effective_openai_key()` / `get_effective_google_maps_key()` / `get_effective_gemini_key()` / `get_effective_tavily_key()`
- 均遵循：`ContextVar 覆盖值 or .env 默认值`

### 6.5 各服务改动
| 文件 | 改动 |
|------|------|
| `agents/triage_agent.py` | 新增 `_get_client()` / `_is_enabled()`，动态使用 per-request OpenAI Key |
| `services/google_maps_skill.py` | 使用 `get_effective_google_maps_key()` |
| `services/web_search_skill.py` | 使用 `get_effective_tavily_key()` |
| `services/geocode_service.py` | 使用 `get_effective_google_maps_key()` |

### 6.6 请求头约定
| 请求头 | 对应服务 |
|--------|---------|
| `X-OpenAI-Key` | OpenAI GPT Triage Agent |
| `X-Google-Maps-Key` | Google Maps 机构搜索 & Geocode |
| `X-Gemini-Key` | Gemini Navigation Agent（预留） |
| `X-Tavily-Key` | Tavily 症状参考搜索 |

## 7. 当前已落地保证
1. 分诊可输出具体科室（眼科/耳鼻喉/骨科等）或 Primary Care。
2. follow-up 动态生成且去重。
3. 推荐结果提供 `visit_needed`，支持前端”无需进入下一阶段”的业务分支。
4. 位置支持文本 geocode + 前端 GPS 兜底。
5. 前端可通过请求头覆盖任意 API Key，后端无需重启即时生效。
