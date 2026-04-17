# Healthcare-guidance

基于你确认的前端页面（`front.jsx`）落地的全栈项目：
- 前端：React + Vite + Tailwind（保留原始页面结构与交互）
- 后端：FastAPI + LangChain 多 Agent
  - Agent 1（GPT / ChatGPT）：症状分析与分诊推荐
  - Agent 2（Gemini）：基于分诊结果进行机构搜索、保险与费用估算
  - Google Maps skill：通过 Google Places API 搜索附近门诊/医院

## 目录

```text
Healthcare-guidance/
  frontend/
    src/App.jsx
    src/api.js
  backend/
    app/main.py
    app/api/v1/
    app/agents/triage_agent.py
    requirements.txt
  docs/
    frontend_落地架构.md
    backend_落地架构.md
```

## 功能流（已落地）

1. `INTAKE` 症状输入
2. `FOLLOW_UP` 追问
3. `TRIAGE_READY` 推荐确认（同意/不同意）
4. `PROVIDER_MATCHED` 机构匹配
5. `INSURANCE` 保险查询
6. `INSURANCE_RESULT` 结果展示
7. `BOOKING` 预约意向提交
8. `COMPLETED` 完成页

## 后端启动

```bash
cd /Users/jackiewen/Documents/IBM-violet-trio/Healthcare-guidance/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 填写 OPENAI_API_KEY / GEMINI_API_KEY / GOOGLE_MAPS_API_KEY
python run.py
```

服务默认地址：`http://127.0.0.1:8000`

## 前端启动

```bash
cd /Users/jackiewen/Documents/IBM-violet-trio/Healthcare-guidance/frontend
npm install
npm run dev
```

前端默认地址：`http://127.0.0.1:5173`

可选环境变量（前端）：
- `VITE_API_BASE_URL`，默认 `http://127.0.0.1:8000`

## 已实现 API

- `POST /api/v1/triage/sessions`
- `POST /api/v1/triage/sessions/{session_id}/answers`
- `GET /api/v1/triage/sessions/{session_id}/recommendation`
- `POST /api/v1/triage/sessions/{session_id}/recommendation-feedback`
- `POST /api/v1/providers/search`
- `POST /api/v1/insurance/check`
- `POST /api/v1/booking/intents`
- `GET /api/v1/triage/sessions/{session_id}/summary`
- `GET /api/health`

## LangChain 多 Agent 说明

- GPT Triage Agent: `backend/app/agents/triage_agent.py`
  - 负责接收患者描述与追问答案，产出 `department/care_path/reasons/risk_level`
- Gemini Navigation Agent: `backend/app/agents/navigation_agent.py`
  - 负责接收 GPT 分析结果，做机构搜索与保险金额估算
- Google Maps skill: `backend/app/services/google_maps_skill.py`
  - 有 `GOOGLE_MAPS_API_KEY` 时调用 Google Places
  - 无 key 时回退到本地 provider 数据

## 注意事项

1. 当前 provider 与保险估算为 MVP mock 数据，结构已按前端页面需要对齐。
2. 医疗建议仅为导诊，不是医学诊断。
3. 若检测到高危症状（red flags），前端会进入 `ESCALATED` 提示。
