# QuantifyU — AI 量化约会 App

> AI Looksmaxxing 五维评分 + 加权余弦相似度智能匹配 + 最高级别隐私保护

**Tech Stack:** React Native (Expo 52) · FastAPI · Supabase · ViT-FBP · MediaPipe · AES-256-GCM

---

## 项目结构

```
quantifyu/
├── apps/mobile/          # React Native + Expo Router
│   ├── app/              # 屏幕 (auth, tabs)
│   ├── components/       # UI, privacy, score 组件
│   ├── lib/              # api, crypto, constants
│   ├── store/            # Zustand 全局状态
│   └── types/            # TypeScript 类型定义
├── services/api/         # FastAPI 后端
│   ├── app/
│   │   ├── routers/      # 7 个路由模块
│   │   ├── schemas/      # Pydantic 模型
│   │   ├── services/     # AI 引擎, 匹配, 加密
│   │   ├── middleware/    # JWT 认证, Consent 检查
│   │   └── utils/        # AES-256-GCM, 照片哈希
│   └── tests/            # pytest 测试套件
├── supabase/migrations/  # SQL 迁移
└── docker-compose.yml    # 本地开发
```

---

## 1. 开发流程 Checklist（从零到上线）

### Phase 1: 环境准备

```
[ ] 1.1  安装前置依赖
         - Node.js 20+ / pnpm or npm
         - Python 3.11+
         - Docker Desktop
         - Supabase CLI: npm i -g supabase
         - Expo CLI: npm i -g eas-cli
         - Railway CLI: npm i -g @railway/cli

[ ] 1.2  克隆项目
         git init
         git add .
         git commit -m "Initial commit: QuantifyU MVP"

[ ] 1.3  创建 Supabase 项目
         - 访问 https://supabase.com/dashboard → New Project
         - 记录: Project URL, anon key, service_role key, JWT secret
```

### Phase 2: 数据库初始化

```
[ ] 2.1  运行主 Schema
         打开 Supabase SQL Editor → 粘贴 quantifyu_schema.sql → Run

[ ] 2.2  运行隐私加固迁移
         粘贴 supabase/migrations/002_privacy_hardening.sql → Run

[ ] 2.3  验证 RLS
         在 Supabase Dashboard → Authentication → Policies
         确认 8 张表全部启用 RLS

[ ] 2.4  创建 Storage Buckets
         Supabase Dashboard → Storage → 创建:
         - avatars (public, 5MB, image/*)
         - score-photos (private, 10MB, image/*)
```

### Phase 3: 后端启动

```
[ ] 3.1  配置环境变量
         cd services/api
         cp .env.example .env
         # 填入 Supabase 凭证和生成的加密密钥:
         python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"

[ ] 3.2  安装 Python 依赖
         python3 -m venv .venv
         source .venv/bin/activate
         pip install -r requirements.txt

[ ] 3.3  启动开发服务器
         uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

[ ] 3.4  验证 API
         curl http://localhost:8000/health
         # → {"status":"healthy","service":"quantifyu-api","version":"1.0.0"}
         open http://localhost:8000/docs  # Swagger UI
```

### Phase 4: 运行测试

```
[ ] 4.1  运行测试套件
         cd services/api
         python3 -m pytest tests/ -v --tb=short

[ ] 4.2  关键测试验证
         python3 -m pytest tests/test_scoring_genital.py -v -s
         # 输出 6.5 inch 评分详情

         python3 -m pytest tests/test_encryption.py -v
         # 验证 AES-256-GCM + AAD 绑定

         python3 -m pytest tests/test_matching_engine.py -v -s
         # 输出匹配兼容度计算详情
```

### Phase 5: 前端启动

```
[ ] 5.1  配置环境变量
         cd apps/mobile
         cp .env.example .env
         # 填入 API URL 和 Supabase 凭证

[ ] 5.2  安装依赖
         npm install

[ ] 5.3  启动 Expo 开发服务器
         npx expo start

[ ] 5.4  在模拟器/真机测试
         按 i → iOS Simulator
         按 a → Android Emulator
         扫码 → 真机 Expo Go
```

### Phase 6: 端到端验证

```
[ ] 6.1  注册流程
         Onboarding 4步 → 同意条款 → 创建账号

[ ] 6.2  AI 评分流程
         上传面部照片 → 扫描动画 → 填写身体数据 → 查看五维评分

[ ] 6.3  私密数据流程
         启用 genital consent → 输入自测数值 → 验证加密存储

[ ] 6.4  匹配流程
         发现页滑动 → 查看兼容度 → Like/Pass

[ ] 6.5  隐私管理
         设置 → 隐私管理 → 撤回 consent → 验证数据已删除
```

### Phase 7: 部署上线

```
[ ] 7.1  后端部署到 Railway（见下方命令）
[ ] 7.2  更新前端 .env 指向生产 API URL
[ ] 7.3  EAS Build → TestFlight / Internal Testing
[ ] 7.4  配置自定义域名 + TLS
[ ] 7.5  配置 Supabase 生产环境
         - 启用 Email confirmation
         - 设置 SMTP
         - 配置 Rate Limiting
```

---

## 2. 部署命令

### 后端 → Railway

```bash
# ---- 首次部署 ----

# 安装 Railway CLI
npm i -g @railway/cli

# 登录
railway login

# 在 services/api 目录初始化项目
cd services/api
railway init

# 配置环境变量（在 Railway Dashboard 或 CLI）
railway variables set SUPABASE_URL="https://xxx.supabase.co"
railway variables set SUPABASE_SERVICE_ROLE_KEY="eyJ..."
railway variables set SUPABASE_JWT_SECRET="your-jwt-secret"
railway variables set ENCRYPTION_MASTER_KEY="your-base64-key"
railway variables set ENCRYPTION_KEY_VERSION="1"
railway variables set API_ENV="production"
railway variables set API_CORS_ORIGINS="https://your-app-domain.com"
railway variables set MODEL_DEVICE="cpu"
railway variables set VIT_FBP_MODEL_PATH="./app/ai/models/vit_fbp.pth"

# 部署（自动检测 Dockerfile）
railway up

# 查看日志
railway logs

# 获取部署 URL
railway domain
# → https://quantifyu-api-production.up.railway.app
```

```bash
# ---- 后续更新 ----
cd services/api
railway up
```

### 前端 → Expo (EAS Build)

```bash
# ---- 配置 ----
cd apps/mobile

# 登录 Expo 账号
eas login

# 首次配置（替换 eas.json 中的 projectId）
eas build:configure

# ---- 构建 ----

# iOS 开发版（模拟器）
eas build --platform ios --profile development

# iOS 预览版（TestFlight 内测）
eas build --platform ios --profile preview

# iOS 正式版
eas build --platform ios --profile production

# Android 内测
eas build --platform android --profile preview

# ---- 提交应用商店 ----
eas submit --platform ios
eas submit --platform android
```

### 数据库 → Supabase

```bash
# 使用 Supabase CLI 推送迁移
supabase login
supabase link --project-ref YOUR_PROJECT_REF

# 推送 Schema
supabase db push

# 或手动在 SQL Editor 中运行:
# 1. quantifyu_schema.sql
# 2. supabase/migrations/002_privacy_hardening.sql
```

### Docker（本地/自托管）

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f api

# 停止
docker-compose down
```

---

## 3. 测试用例

### 运行全部测试

```bash
cd services/api
source .venv/bin/activate
python3 -m pytest tests/ -v -s
```

### 关键测试场景

#### 3a. 6.5 英寸生殖器官评分

```bash
python3 -m pytest tests/test_scoring_genital.py::TestGenitalScoring::test_65_inch_full_scoring -v -s
```

预期输出:
```
6.5 inch 完整评分: 7.4/10
  长度分: 7.6  (16.51cm, 高于平均 26%)
  周长分: 6.3  (13.0cm, 略粗于平均)
  修饰分: 8.0  (4/5 级修饰)
  自评分: 8.0  (自信)

完整评分 (含 6.5 inch genital):
  面部:      30/40
  身材:      18/25
  身高:      12/15
  皮肤头发:  7/10
  生殖器官:  7.4/10 (6.5 inch)
  ─────────────
  总分:      74.4/100
  评级:      良好
```

#### 3b. 加密安全测试

```bash
python3 -m pytest tests/test_encryption.py -v
```

验证:
- AES-256-GCM 加密/解密往返
- 每字段独立 IV
- AAD 绑定（错误 user_id 解密失败）
- HMAC-SHA256 完整性
- 照片哈希去重
- 内存安全清除

#### 3c. 匹配引擎测试（含 genital 维度）

```bash
python3 -m pytest tests/test_matching_engine.py::TestMatchingEngine::test_genital_65_inch_scoring_example -v -s
```

预期输出:
```
6.5 inch (16.5cm) 生殖器官评分测试结果:
============================================================
  兼容度: ~68%
  余弦相似度: 0.987
  各维度匹配:
    face: 75.0
    body: 72.0
    height: 80.0
    skin_hair: 70.0
    genital: 75.0
  解释: 面部、身高、生殖器官高度匹配
  亮点:
    - 生殖器官高度匹配 (75分) — 对方较看重此项 (15%权重)
    - 评分轮廓较为相似 — 整体趋势一致
============================================================
```

#### 3d. API 端到端测试 (cURL)

```bash
# 注册
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@quantifyu.com",
    "password": "Test1234",
    "display_name": "测试用户",
    "date_of_birth": "1998-05-15",
    "gender": "male",
    "consent_terms_of_service": true,
    "consent_privacy_policy": true,
    "consent_ai_scoring": true,
    "consent_genital_data": true
  }'

# 保存 access_token
TOKEN="eyJ..."

# 保存私密数据（6.5 inch = 16.51cm）
curl -X POST http://localhost:8000/private-vault/save \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "penis_length_cm": 16.51,
    "penis_girth_cm": 13.0,
    "penis_erect_length_cm": 16.51,
    "penis_erect_girth_cm": 13.0,
    "grooming_level": 4,
    "self_rating": 8
  }'
# → 响应: "已加密保存 6 个敏感字段 (AES-256-GCM)"

# 查看 consent 状态
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/privacy/consent/status

# 导出个人数据 (GDPR)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/privacy/data-export
```

---

## 4. 下一步迭代建议

### v1.1 — 核心增强 (2-3 周)

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 实时聊天 | Supabase Realtime + messages 表已就绪 | P0 |
| 照片裁剪/压缩 | expo-image-manipulator 减少上传大小 | P0 |
| Push 通知 | 新匹配/新消息通知 (expo-notifications) | P0 |
| 速率限制 | fastapi-limiter 防止 API 滥用 | P0 |
| ViT-FBP 模型部署 | 下载预训练权重到 Railway 或 GPU 云 | P1 |

### v1.2 — 商业化 (1-2 月)

| 功能 | 说明 | 优先级 |
|------|------|--------|
| Premium 订阅 | RevenueCat + Stripe, 解锁无限评分/超级喜欢 | P0 |
| 财务评分维度 | 新维度: income/assets/career (自报 + 验证) | P1 |
| 社交验证 | Instagram/LinkedIn OAuth 增加可信度 | P1 |
| 举报系统 | 用户举报 + 管理员审核面板 | P1 |

### v1.3 — 创作者经济联动 (2-3 月)

| 功能 | 说明 | 技术方案 |
|------|------|----------|
| OnlyFans 联动 | 高分用户可选择展示 OF 链接 | profiles 表加 `creator_links JSONB`, 仅 matched 用户可见 |
| 创作者认证 | 验证 OF/Fansly 账号真实性 | OAuth 或手动审核, `is_verified_creator` flag |
| 创作者评分加成 | 认证创作者获得曝光加权 | 匹配算法加 `creator_boost` 参数 |
| 收入展示 (可选) | 创作者可选择展示月收入范围 | AES 加密存储, 类似 vault 架构 |
| 合作匹配 | 创作者之间的合作配对 | 新 `collaboration_matches` 表, 独立于约会匹配 |

### v1.4 — 高级 AI (3+ 月)

| 功能 | 说明 | 技术方案 |
|------|------|----------|
| AI 改善建议 | GPT-4V 生成个性化 Looksmaxxing 建议 | Claude/GPT API, 基于评分 breakdown |
| 风格推荐 | 基于脸型推荐发型/穿搭 | 额外 CV 模型 + 推荐引擎 |
| 评分趋势 | 历史评分折线图, 改善追踪 | 前端 `react-native-chart-kit` |
| 视频评分 | 30 秒视频 → 动态美学分析 | MediaPipe 逐帧分析, 取平均 |
| 语音评分 | 声音吸引力打分 | Wav2Vec + 自训练声音美学模型 |

### 架构演进路线

```
MVP (当前)                    v2.0                         v3.0
─────────                    ────                         ────
单服务 FastAPI    →    微服务 (评分/匹配/聊天)    →    K8s + GPU 集群
Supabase          →    Supabase + Redis 缓存      →    自建 Postgres + Dragonfly
CPU 推理          →    单 GPU (T4/A10)             →    多 GPU 推理 + 模型并行
Expo Go 测试      →    TestFlight 内测              →    App Store / Play Store
手动部署          →    GitHub Actions CI/CD         →    Argo CD + 灰度发布
```
