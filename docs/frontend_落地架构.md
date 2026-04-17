# 医疗导航 Agent 前端落地架构（基于当前 `frontend/src/App.jsx`）

## 1. 目标
1. 全英文 UI 完成从档案填写到分诊、机构匹配、保险估算、预约意向的全流程。
2. 与后端双 Agent 对齐：GPT 负责分诊，Gemini 负责机构与保险说明。
3. 与后端接口字段保持严格一致，避免前后端契约漂移。

## 2. 当前页面与状态机
主流程状态：
`PROFILE -> INTAKE -> FOLLOW_UP -> TRIAGE_READY -> PROVIDER_MATCHED -> INSURANCE -> INSURANCE_RESULT -> BOOKING -> COMPLETED`

异常/分支状态：
- `ESCALATED`：命中红旗症状时显示急诊提示。
- `TRIAGE_READY` 下自我护理分支：
  - 条件：`department='Primary Care' && care_path='PRIMARY_CARE' && visit_needed=false`
  - 行为：不进入 provider 阶段，只允许 `Back to home` 或 `Rewrite symptoms`。

## 3. Profile 阶段（新增）
`PROFILE` 页面输入字段：
- `detailAddress`
- `city`
- `zipCode`
- `age`（必填）
- `sex`（必填）
- `insurancePlan`（可选）

规则：
1. 三个位置字段至少填写一个，否则前端提示并阻止提交。
2. 点击继续后，先调用 geocode；若 geocode 失败，自动尝试浏览器 GPS。
3. geocode 与 GPS 都失败时，提示用户开启定位或补充位置信息。

## 4. 接口映射（前端真实调用）

### 4.1 位置解析
- 函数：`geocodeLocation(payload)`
- 接口：`POST /api/v1/geo/geocode`

请求：
```json
{ "query": "36 journal square, New Jersey, 07306" }
```

响应：
```json
{
  "query": "36 journal square, New Jersey, 07306",
  "normalized_address": "...",
  "lat": 40.7,
  "lng": -74.0,
  "source": "google|fallback|zip_fallback"
}
```

### 4.2 创建分诊会话
- `POST /api/v1/triage/sessions`

请求：
```json
{
  "user_profile": {
    "age": 32,
    "sex": "female",
    "city": "normalized address or city/zip",
    "insurance_plan": "Aetna PPO"
  },
  "symptom_input": {
    "chief_complaint": "...",
    "duration_hours": 0,
    "severity_0_10": 6,
    "free_text": "..."
  },
  "consent": { "hipaa_ack": true, "ai_guidance_ack": true }
}
```

### 4.3 Follow-up 提交
- `POST /api/v1/triage/sessions/{session_id}/answers`

### 4.4 推荐结果
- `GET /api/v1/triage/sessions/{session_id}/recommendation`
- 响应关键字段（新增）：
```json
{
  "department": "Ophthalmology",
  "care_path": "SPECIALIST",
  "confidence_percent": 86,
  "visit_needed": true,
  "reasons": ["..."],
  "red_flags_detected": []
}
```

### 4.5 推荐反馈
- `POST /api/v1/triage/sessions/{session_id}/recommendation-feedback`

### 4.6 机构搜索
- `POST /api/v1/providers/search`

请求（前端最终保证传 `city + lat + lng`）：
```json
{
  "session_id": "sess_xxx",
  "care_path": "URGENT_CARE",
  "location": {
    "city": "Jersey City, NJ",
    "lat": 40.7,
    "lng": -74.0,
    "radius_km": 10
  }
}
```

### 4.7 保险与预约
- `POST /api/v1/insurance/check`
- `POST /api/v1/booking/intents`
- `GET /api/v1/triage/sessions/{session_id}/summary`

## 5. 前端关键交互约束
1. 推荐页 `Agree` 只有在 `visit_needed=true` 时才进入 provider 搜索。
2. `visit_needed=false` 的 Primary Care 分支必须直接终止医疗机构匹配流程。
3. 进度条首阶段为 `Profile`，不可跳过。
4. 错误提示统一展示后端 `detail` 或拼接后的校验错误。

## 6. API Key 设置（2026-04-17 新增）

### 6.1 入口
- Header 右上角的 **"API Keys"** 按钮（Settings 图标），全流程可见。

### 6.2 `ApiKeyModal` 组件
- 四个输入字段：OpenAI API Key / Google Maps API Key / Gemini API Key / Tavily API Key。
- 每个字段支持 show/hide 切换（密码模式）。
- **Save**：将非空值写入 `localStorage`，空值删除对应 key。
- **Clear all**：清空所有已存储 key。
- 点击 backdrop 或 Cancel 直接关闭不保存。

### 6.3 `api.js` 中的 Key 注入
- `getStoredApiKeys()`：读取 localStorage 中的四个 key。
- `saveApiKeys()`：写/删 localStorage。
- `getApiKeyHeaders()`：将有值的 key 组装为请求头（`X-OpenAI-Key` / `X-Google-Maps-Key` / `X-Gemini-Key` / `X-Tavily-Key`）。
- `request()` 自动附加这些请求头，所有接口调用均生效。

### 6.4 优先级规则
- 用户在弹窗填写的 Key → 优先使用（通过请求头传给后端）。
- 未填写 → 后端使用 `.env` 中的默认 Key，前端无感知。
