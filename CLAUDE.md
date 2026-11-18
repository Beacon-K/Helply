# Helply — 给 Claude Code 的项目说明

> 会话开始先读本文件，再读 `PROGRESS.md`（进度、待办、决定）。具体实现细节看代码和 docstring，这里不重复。

## 项目是什么
Helply 是 Fanshawe College BIA 毕业设计（4 人小组，负责人 Kevin）：面向 **10–100 人中小企业** 的 IT 服务台 / ITSM。
- 定位：服务大型 ITSM 覆盖不到的中小企业，**不要**包装成和 Jira 竞争。
- AI 必须嵌入业务流程（分类、分派、相似工单、监控告警建工单），不是单独的聊天框。
- **按可直接上生产的标准开发**，不是演示原型。

## 与 Kevin 协作的规则
- **用中文回复**，简洁，多用表格，坦诚；**不编造数字**。
- UI 标准：**Awwwards / Webby / FWA 水准**。改页面要截图自检、多轮迭代，桌面和手机宽度都看；可以推翻现有 UI。
- 展示真实资源的页面（如 Cloud servers）**绝不放假数据**。
- 安全：
  - 密钥、令牌、密码不出现在聊天里，也不写进代码；Cloudflare 隧道令牌由 Kevin 自己写进 `.env`。
  - 仓库是 **Public**：不提交个人评审、有版权的图片；`.env`、`db.sqlite3*`、`tools/cloudflared*`、`backups/`、`logs/` 不提交。
  - 下载任何东西前，先说明文件名、来源和大小。
  - 监控 agent 必须**只读**，永远不接受远程命令。
- **数据库是唯一的事实来源**：启动脚本、种子命令、迁移都不能覆盖已有数据（人员、角色、密码、SLA、工单、资产、知识库）。重置只能由 Kevin 明确触发（`reset-demo.bat`）。密码只在建号时设置一次，之后归用户所有。
- 只在 Kevin 要求时 commit / push。提交前跑完整测试并扫描密钥。
- 改 `.bat` 后确认是 **CRLF**（Git Bash 里的 python 写出来是 LF，会坏掉批处理）。

## 技术栈
- Django 6.1（Python 3.12+），默认 SQLite（WAL + `transaction_mode=IMMEDIATE`），可选 PostgreSQL 17。
- Waitress + WhiteNoise；公网走 Cloudflare Tunnel（helply.work）。
- 前端：Django 模板 + 原生 JS + 手写 CSS，**不用框架、不用 CDN**（要能离线演示）。

## 代码结构
| 位置 | 内容 |
|---|---|
| `apps/accounts` | User（employee / technician / administrator）、Department、SupportGroup；People 页（仅管理员，新人用一次性链接设密码） |
| `apps/tickets` | 工单；状态机 `workflow.py`；ITIL 优先级矩阵 `choices.py` |
| `apps/sla` | SLA 策略与 `/sla/` 设置页 |
| `apps/assets` | 资产台账（`live.py` 实时版本号）；IT 人员在站内增删改，不再依赖 Django Admin（侧栏已无 Admin 入口，`/admin/` 仅作后备） |
| `apps/kb` | 知识库；所有 IT 人员（技术员和管理员）可在站内增删改文章，员工只读（`seed_kb` 只新增，`--overwrite` 才覆盖） |
| `apps/ai` | 分类后端（关键词基线；`backends/` 下可选 Cloudflare、OpenAI/Anthropic，失败退回关键词）、`assistant.py`、`chat.py`（Ctrl/Cmd+J 抽屉）、`insights.py`、`metering.py`；接口 `/ai/`；`python manage.py ai_status --test` 检查。密钥只放 `.env` |
| `apps/notifications` | 站内铃铛 + 邮件，按「工单 + 类型」节流 |
| `apps/monitoring` | 云服务器监控：上报 API、告警转工单、`presenters.py`、`geo.py` |
| `apps/core` | 仪表盘（`views.py`、`overview.py`）、演示数据（`demo/`）、运维命令；`middleware.py` 让登录页面不可缓存 |
| `agent/` | 监控 agent 和安装脚本 |
| `templates/`, `static/` | **`calm.css` 最后加载，决定最终外观**（中性色阶 + 唯一强调色，无渐变/光斑/毛玻璃，按钮 10px 圆角，字重 400–600）；改外观先改它，不要往前面几层加装饰。颜色一律用变量（`theme.css`）；触屏点击区域 ≥ 36px；登录页是 `base_landing.html` + `landing.css` + `landing.js`：一屏幻灯片（`data-slide` 卡片叠放，滚轮/滑动/方向键/圆点切换，卡片内容过高时在卡片内部滚动；没有 JS 时退回普通长页面） |

## 常用命令
```bash
python manage.py test                     # 全部约 9 分钟；小改动只跑相关 app，如 apps.ai
python manage.py seed_demo               # 只补缺少的演示数据（production 下拒绝）
python manage.py seed_demo --reset --overwrite  # 有意重置演示（或 reset-demo.bat）
python manage.py demo_passwords --rotate # 有意换全部演示账号密码
python manage.py run_jobs --every 5       # SLA、跟进、监控、续费提醒、每日备份
python manage.py init_helply              # 真实公司首次初始化
python manage.py backup_db
```
- 启动脚本：`setup.bat`、`start-demo.bat`、`start-online.bat`、`reset-demo.bat`、`start-production.bat`、`update-online.bat`（拉取最新代码并重启公网站点，数据不动）；Linux 用 `setup.sh`、`start-demo.sh`。
- 每台机器独立虚拟环境 `.venv-%COMPUTERNAME%`（`tools/helply-env.bat`）。
- `HELPLY_ENVIRONMENT`：`development` | `demo` | `production`。production 要求 `DJANGO_SECRET_KEY` ≥ 40 字符。
- 公网模式只在设置了 `HELPLY_PUBLIC_HOST` 时开启（由启动脚本设置，**不要**写进 `.env`）。

## 代码风格
- 跟随周围写法；注释说明「为什么」。
- 新页面的静态文件要加进 `apps/core/context_processors.py` 的 `ASSET_FILES`。
- 外部数据（如 agent 上报）一律校验并限制范围（参考 `monitoring/services.py` 的 `_number`、`_text`）。
- **英语 / 法语双语**（Django i18n，`locale/fr/LC_MESSAGES/django.po`）：页面文字写 `{% trans %}` / `{% blocktrans %}`，Python 里用 `gettext` / `gettext_lazy`（不要把 `_` 当临时变量）；数据库里用户写的内容不翻译。本机没有 GNU gettext，流程是 `python tools/extract_messages.py` → 在 .po 里补法语 → `python tools/compile_messages.py`，**.mo 要一起提交**（`test_i18n` 会检查 .mo 没过期、占位符没丢）。语言用 `django_language` cookie（页面右上角 EN/FR），没选过就看浏览器语言。目前已翻译：登录与重置密码、侧栏/顶栏、仪表盘、工单列表/详情/新建、通知、助手抽屉；**还没翻译**：Help tour 与 Ctrl+K 面板（JS）、知识库、资产、云服务器、人员、SLA 页、邮件正文。
