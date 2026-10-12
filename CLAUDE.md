# Helply — 给 Claude Code 的项目说明

> 每次会话开始先读本文件，再读根目录的 `PROGRESS.md`（需求、进度、待办）。

## 项目是什么
Helply 是 Fanshawe College BIA 毕业设计（4 人小组，负责人 Kevin）：面向 **10–100 人中小企业** 的 IT 服务台 / ITSM。
- 定位：服务大型 ITSM（ServiceNow、Jira SM）覆盖不到的中小企业。**不要**把它包装成和 Jira 竞争。
- AI 必须嵌入业务流程（自动分类、自动分派、相似工单、监控告警自动建工单），而不是一个单独的聊天框。
- **按真实业务、可直接上生产的标准开发**，不是演示原型。数据库是唯一的事实来源（例如知识库以数据库为准）。

## 与 Kevin 协作的规则
- **用中文回复**，简洁，多用表格，坦诚；**不编造数字**。
- UI 质量标准：**Awwwards / Webby / FWA 获奖水准**。改页面要截图自检、多轮迭代，桌面和手机宽度都要看；可以推翻现有 UI。
- 展示用户真实资源的页面（例如 Cloud servers）**绝不放假数据**。
- 安全：
  - 密钥、令牌、密码不出现在聊天里，也不写进代码。Cloudflare 隧道令牌由 Kevin 自己粘贴进 `.env`。
  - 仓库保持 **Private**；`.env`、`db.sqlite3*`、`tools/cloudflared*`、`backups/`、`logs/` 不提交。
  - 下载任何东西前，先说明文件名、来源和大小。
  - 监控 agent 必须**只读**，永远不接受远程命令。
- **数据库是唯一的事实来源**：启动脚本、种子命令、迁移都不能覆盖或重置已有数据（人员、角色、密码、SLA、工单、资产）。重置只能由 Kevin 明确触发（`reset-demo.bat`）。密码只在账号创建时设置一次，之后归用户所有，不得自动重置。
- 只在 Kevin 要求时 commit / push。提交前跑完整测试，并扫描有没有密钥。
- 改 `.bat` 文件后确认是 **CRLF** 换行（Git Bash 里的 python 写出来是 LF，会坏掉批处理）。

## 技术栈
- Django 6.1（需要 Python 3.12+），默认 SQLite（开启 WAL 和 `transaction_mode=IMMEDIATE`），可选 PostgreSQL 17。
- Waitress + WhiteNoise；公网访问走 Cloudflare Tunnel（helply.work，DNS 托管在 Cloudflare）。
- 前端：Django 模板 + 原生 JS + 手写 CSS，**不用框架、不用 CDN**（要能离线演示）。

## 代码结构
| 位置 | 内容 |
|---|---|
| `apps/accounts` | User（角色：employee / technician / administrator）、Department、SupportGroup；People 页面（`views.py`、`forms.py`，仅管理员；新人用一次性链接设密码，不碰明文密码） |
| `apps/tickets` | 工单；状态机在 `workflow.py`；ITIL 优先级矩阵在 `choices.py` |
| `apps/sla` | SLA 策略：暂停/恢复、即将超时、已超时；`/sla/` 设置页（时间写成 `30m`、`4h`、`1d 2h`） |
| `apps/assets` | 资产台账，`live.py` 提供实时版本号 |
| `apps/kb` | 知识库（Markdown，数据库为准；`seed_kb` 只新增，`--overwrite` 才覆盖） |
| `apps/ai` | 关键词基线分类器（可替换后端；`backends/cloudflare.py` 可选接 Cloudflare Workers AI，失败自动退回关键词；`assistant.py` 是 Helply Assistant：员工在工单创建页/知识库页提问（只依据知识库和本人历史工单），技术员在工单详情页用 copilot；`chat.py` 是主窗口右侧的助手抽屉（Ctrl/Cmd+J，多轮真实对话，默认用 `HELPLY_CF_CHAT_MODEL` 的 70B 模型；三种角色；公司事实只依据传入的数据，模型回复末尾的 BASIS/SOURCES 标记由代码校验，一般 IT 常识会标注「不是知识库」）；`insights.py` 是管理员的工单分析（代码统计数字、模型只解释原因和预防，仪表盘卡片，`ai_insights` 命令每天由 run_jobs 刷新）；接口在 `/ai/`，每人每小时有次数上限）、AISuggestion 反馈、准确率 |
| `apps/notifications` | 站内铃铛 + 邮件，按「工单 + 类型」节流 |
| `apps/monitoring` | 云服务器监控：模型、上报 API、告警转工单、`presenters.py`（页面和 JSON 数据）、`geo.py`（按 IP 在本地查国家，数据库在 `data/`）、`countries.py` |
| `apps/core` | 仪表盘（`views.py`；公司概况数据在 `overview.py`：未分配工单、人员、云服务器、续费）、演示数据（`demo/`）、生产运维命令 |
| `agent/` | 监控 agent（`helply_agent.py`）和 `install.sh` / `install.ps1` |
| `templates/`, `static/css`, `static/js` | 模板、样式和脚本；监控模块用 `monitoring.css`、`fleet.js`、`fleet-detail.js`；白天/夜间主题是 `theme.css` + `theme.js`（颜色一律用变量，不要写死）；登录后的整体质感（毛玻璃栏、大字标题、圆角卡片、药丸按钮、分段筛选）在 `apple.css`；其后最后加载的 `tech.css` + `tech.js`（助手面板样式也在 tech.css，脚本是 `assistant.js`） 是「控制台质感」（命令面板 Ctrl/Cmd+K、`g` 快捷键、光斑、悬停高亮）；登录页是独立的 `base_landing.html` + `landing.css`；国旗在 `static/img/flags/` |

## 常用命令
```bash
python manage.py test                     # 全部测试（目前 273 项）
python manage.py seed_demo               # 只补缺少的演示数据，已有的一律不动（生产环境下拒绝执行）
python manage.py seed_demo --reset --overwrite  # 有意重置演示：删全部工单、演示人员/SLA/资产恢复原值（或运行 reset-demo.bat）
python manage.py demo_passwords --rotate # 有意给全部演示账号换一批随机密码
python manage.py run_jobs --every 5       # SLA 检查、跟进、监控检查、每日备份
python manage.py monitor_check --every 30 # 离线检测 + 指标汇总 + 清理超时未接入的占位服务器
python manage.py init_helply              # 真实公司首次初始化
python manage.py backup_db
```
- Windows 启动脚本：`setup.bat`、`start-demo.bat`、`start-online.bat`、`reset-demo.bat`（有意重置演示）、`start-production.bat`；Linux 用 `setup.sh` 和 `start-demo.sh`。
- 每台机器用独立的虚拟环境 `.venv-%COMPUTERNAME%`，由 `tools/helply-env.bat` 选择。
- 运行模式由环境变量 `HELPLY_ENVIRONMENT` 决定：`development` | `demo` | `production`。production 要求 `DJANGO_SECRET_KEY` 至少 40 个字符；演示数据命令在 production 下拒绝执行，在库里有非演示账号时也拒绝执行（`apps/core/demo/guard.py`）。
- 公网模式只在设置了 `HELPLY_PUBLIC_HOST` 时开启（由启动脚本设置，**不要**写进 `.env`）。

## 代码风格
- 跟随周围代码的写法；docstring 和注释要说明「为什么」。
- 新页面的静态文件要加进 `apps/core/context_processors.py` 的 `ASSET_FILES`，这样文件更新后浏览器会拿到新版本。
- 来自外部的数据（例如 agent 上报）全部要校验、做范围限制（参考 `monitoring/services.py` 里的 `_number` 和 `_text`）。
