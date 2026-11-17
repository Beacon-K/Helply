# Helply 进度与交接（截至 2026-11-17）

## 1. 需求
| 类别 | 要求 |
|---|---|
| 用户 | 10–100 人中小企业；IT 团队 1–5 人 |
| 核心 | 工单、SLA、资产、知识库、通知、仪表盘 |
| AI | 嵌入流程：自动分类分派、相似工单、知识库建议、监控告警建工单 |
| 质量 | 可上生产；数据库是唯一事实来源；UI 获奖水准 |
| 部署 | 演示：外接硬盘 + SQLite，两台电脑切换；公网 https://helply.work（Cloudflare Tunnel） |
| 不做 | Microsoft 365 登录、真实用户数据导入、堡垒机 |

## 2. 已完成
| 模块 | 内容 |
|---|---|
| 工单 | 状态机、ITIL 优先级矩阵、公开回复/内部备注、审计、满意度、超时自动关闭 |
| SLA | 按优先级策略、暂停/恢复、提醒、超时；`/sla/` 设置页（只影响新工单） |
| AI | 关键词分类 + 自动分派（最少工作量）、相似工单、反馈准确率；可选 Cloudflare / OpenAI / Anthropic 后端；Assistant、Ctrl/Cmd+J 助手抽屉、管理员工单分析、Cloudflare 额度统计与提醒 |
| 知识库 | 44 篇文章、投票、提单时推荐 |
| 通知 | 站内铃铛 + 邮件（Brevo），按「工单 + 类型」节流；续费提醒 30/14/7 天和当天 |
| 资产 | 106 条数据；Excel 导出和批量导入（先预览）；实时刷新；重复故障提示 |
| 人员 | `/people/` 仅管理员：搜索筛选、新增编辑、关闭登录、一次性设密码链接；不能降级或关闭自己，始终保留一个管理员 |
| 仪表盘 | 管理员和技术员的未分配工单、Company overview（云服务器、人员、续费与资产） |
| 界面 | 登录页是产品介绍页；控制台质感（Ctrl/Cmd+K、`g` 快捷键）；`calm.css` 统一配色；白天/夜间主题；Help 互动教程；部门和团队管理页 |
| 安全 | 登录限流和登录记录、Admin 外观统一、邮件后台发送 |
| 生产化 | 三种运行模式、演示数据保护、`init_helply`、`backup_db`、`run_jobs`、部署检查 `helply.W001–W003` |
| 邮件 | 2026-10-03 验证：Brevo 发出，Cloudflare Email Routing 转发收到。SMTP 配置在 `.env`（凭据由 Kevin 填）；key 约 2027-10-03 到期。Brevo 会拉黑硬退信地址，新增收件域名前先确认能收信。**不往保留假域名发信**（`example.*`、`*.test` 等）。演示邮箱统一 `用户名@helply.work`。详见 README「邮件发送（Brevo）」 |
| 报告 | 已交 5 页英文报告（Word，不在仓库里） |

## 3. 云服务器监控（apps/monitoring）
| 部分 | 状态 |
|---|---|
| Agent | `agent/helply_agent.py` v1.1.0：Python + psutil，10 秒 HTTPS 上报；**只读**；识别云服务商、地区、机型 |
| 安装 | Linux systemd（低权限、64 MB 限制）；Windows 计划任务（Local Service）；都支持卸载 |
| 接入 | Add server → 一行安装命令（令牌只显示一次）→ 首次上报自动填信息；费用、续费日期、负责人选填 |
| 身份 | 每台一个令牌，库里只存 SHA-256；`POST /monitoring/api/report/`，`Authorization: Bearer` |
| 告警 | 离线 > 2 分钟、CPU/内存持续 5 分钟 ≥ 90%、磁盘 ≥ 90% → 自动建工单并分派、启动 SLA；恢复留记录不自动关；支持维护模式 |
| 保留 | 原始读数 48 小时，小时汇总 90 天；24 小时未接入的占位服务器自动清理 |
| 页面 | 总览（卡片/表格、5 秒刷新）、详情（4 张图表）、接入页、设置页；国家和国旗按 IP 本地查（DB-IP，CC BY 4.0，总览页有署名），可手动改 |
| 资产联动 | 每台服务器自动生成 `VPS-xxxx` 资产，年费计入订阅 |
| 演示数据 | **不生成假服务器** |
| 验证 | 自动化、HTTP 端到端、浏览器测试已过；**还没在真实 VPS 上跑过 agent** |

## 4. 待办
| # | 事项 | 说明 |
|---|---|---|
| 1 | 真实服务器实测 agent | 目标机器见第 6 节 |
| 2 | 推送代码 | Kevin 要求时再推送（仓库 Public） |
| 3 | 学校服务器迁移 | 等学校确认能否长期运行、能否用 Cloudflare 隧道；确认后写开机自启脚本和迁移清单 |
| 4 | 监控第 2 阶段 | 费用汇总报表、访问登记 |
| 5 | 邮件转工单 | 用 Email Routing 把 `support@helply.work` 转进 Helply 解析成工单；**还没做** |
| 6 | 可选 | agent 打包成 exe |
| 7 | 测试提速 | 全部约 9 分钟，找最慢的测试 |

已完成：helply.work 公网访问（2026-10-03，cloudflared 用 `--protocol http2`，www 子域名未配置）。

## 5. 已定的决定（不要轻易推翻）
- 自己写 agent，不用 Komari，也不用 SSH 轮询：只读、安全、能和工单集成。
- 演示和生产都优先 SQLite，确实需要才上 PostgreSQL。
- 网站和数据库**不拆到两台 1 GB VPS 上**。
- 两台 OCI VPS 用来被监控和存异地备份。
- 公网用 Cloudflare Tunnel（只往外连）。

## 6. 环境
| 机器 | 说明 |
|---|---|
| KAI-ROG（Windows，Python 3.13） | 主开发机；外接硬盘 `D:\6.Capston Project\helply`；`.venv-KAI-ROG` |
| 第二台 PC（Windows，Administrator，Python 3.14） | 也用外接硬盘 |
| OCI VPS 40.233.75.87（Tailscale 100.96.0.7:9622） | Ubuntu 24.04，1 GB + 2 GB swap；跑 xray、AdGuard、komari agent、WARP；空目录 `/opt/helply` 可删 |
| OCI VPS（Tailscale 100.96.0.5） | 1 GB，swap 用得多 |
| RackNerd 107.173.15.18 | 测试服务器 |
| 学校 Windows Server 2025 | 2 vCPU，15.6 GB；等学校确认 |

## 7. 注意事项
- 新依赖 `maxminddb`：其他机器要重跑 `setup.bat`，否则国家识别静默失效。
- 公网站点的代码和静态文件只在 `start-online.bat` 启动时加载，改完要重启。
- `Images/`（库存图片）和个人评价、渗透测试输出有意不提交。
- 本机没装 psutil，`AgentTests` 会被跳过。
- 演示公司 **100 人**（1 管理员、3 技术员、96 员工，10 个部门；员工用户名是名字小写，如 `ava`），名单固定在 `apps/core/demo/people.py`。
- **启动不改任何数据**：`start-*.bat`、`setup.bat` 只在库里没有用户时生成演示数据。演示密码只在建号时设置（公网模式随机，记在 `demo-passwords.txt`，不提交）。重置用 `reset-demo.bat`（输入 RESET）；换密码用 `demo_passwords --rotate`。`start-online.bat` 同时跑定时任务。
- 在 `127.0.0.1` 打开时，生成的安装命令服务器用不了，必须走公网地址。
- Windows 下 Git 的换行符警告正常；`.gitattributes` 规定 `*.bat` 用 CRLF，`*.sh` 和 `agent/*.py` 用 LF。
