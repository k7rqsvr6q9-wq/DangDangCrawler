# 当当网图书榜单爬虫与数据分析系统

> **V2.1.0** — 分析模块支持按批次筛选不同时间段数据

## 项目简介

当当网图书榜单爬虫与数据分析系统是一款专业的图书市场数据采集与分析工具。系统自动爬取当当网畅销榜和新书热卖榜数据，经过智能清洗后存储至MySQL数据库，并提供6个维度的可视化分析报告。

**解决的核心问题**：当当网页面数据分散、格式不统一，手动收集效率极低。本系统实现了从数据采集、清洗、存储到可视化分析的全流程自动化，特别针对书名中混杂的营销文字、副标题等问题，设计了多策略分隔算法。

## 功能特性

### 爬虫核心
- **多维度爬取**：支持畅销榜/新书热卖榜，覆盖24小时/7日/30日/月度/年度等时间维度
- **智能书名分隔**：多种策略从左到右扫描，自动分离书名与营销文字/副标题/版本信息
- **断点续爬**：根据数据库已有数据自动计算已爬页数，跳过已爬取的页面
- **详情页深度采集**：自动访问图书详情页，提取分类和出版时间
- **数据清洗**：创作者/出版社名称标准化，价格/折扣/评分合理性校验
- **MySQL持久化**：批次管理、数据去重（upsert）、批量删除
- **CSV导出**：支持字段选择，自定义导出内容
- **Web界面**：响应式布局、明暗主题切换、可拖拽分割面板、级联时间选择器
- **反爬策略**：随机User-Agent轮换、请求间隔随机化、重试递增等待

### 数据分析（V2.0.0 新增）
- **分类势力范围**：树状图展示各分类市场份额
- **价格-排名关系**：散点图探索价格、评论数与排名的关联
- **价格-评分组合**：热力图识别黄金定价与评分区间
- **标题关键词**：词云图分析畅销书流量密码
- **出版社实力**：雷达图多维度对比头部出版社
- **排名分层对比**：箱线图揭示不同层级图书特征差异

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| 后端框架 | Flask |
| 前端 | HTML + CSS + JavaScript（原生） |
| 数据库 | MySQL + SQLAlchemy ORM + PyMySQL |
| 爬虫 | Requests + BeautifulSoup4 + lxml |
| 数据分析 | Pandas + NumPy + Matplotlib + Seaborn |
| 可视化 | Squarify + WordCloud + Jieba |
| 包管理 | uv + pyproject.toml |

## 环境准备与安装

### 前置条件

- Python 3.11 或更高版本
- MySQL 5.7+ 或 8.0+（需已启动服务）
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装步骤

1. **克隆项目**

```bash
git clone <项目仓库地址>
cd DangDangCrawler
```

2. **安装依赖**

```bash
uv sync
```

3. **配置数据库**

编辑项目根目录下的 `config.ini` 文件：

```ini
[database]
host = localhost
port = 3306
username = root
password = 你的密码
database = dangdang_data
```

> ⚠️ 请勿将包含真实密码的config.ini提交到版本控制系统

4. **启动应用**

```bash
uv run python main.py
```

启动后自动打开浏览器访问 `http://127.0.0.1:5000`

5. **初始化数据库**

在Web界面点击「初始化数据库」按钮，系统将自动创建数据库和表结构。

6. **运行数据分析**（可选）

```bash
cd analysis
uv run jupyter notebook visualization.ipynb
```

## 项目结构

```
DangDangCrawler/
├── main.py                          # 程序入口
├── config.ini                       # 配置文件
├── config.ini.example               # 配置模板
├── pyproject.toml                   # 项目依赖
│
├── dangdang_crawler/                # 爬虫核心包
│   ├── core/                        # 核心爬虫模块
│   │   ├── spider.py                # 爬虫引擎
│   │   ├── parser.py                # HTML解析器
│   │   ├── cleaner.py               # 数据清洗器
│   │   └── scheduler.py             # 任务调度器
│   ├── database/                    # 数据库模块
│   │   ├── models.py                # ORM模型
│   │   └── connector.py             # 数据库连接器
│   ├── web/                         # Web界面模块
│   │   ├── app.py                   # Flask后端API
│   │   └── templates/
│   │       └── index.html           # 前端界面
│   └── utils/                       # 工具模块
│       ├── config.py                # 配置管理
│       ├── logger.py                # 日志系统
│       └── helpers.py               # 工具函数
│
└── analysis/                        # 数据分析模块（V2.0.0）
    ├── README.md                    # 分析模块说明
    ├── visualization.ipynb          # Jupyter Notebook
    ├── 当当网2025年畅销榜深度分析报告.md  # 分析报告
    └── charts/                      # 图表输出
```

## API接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/start` | 启动爬取任务 |
| POST | `/api/stop` | 停止爬取 |
| POST | `/api/pause` | 暂停/恢复爬取 |
| GET | `/api/status` | 获取爬取状态 |
| POST | `/api/save_db` | 保存数据到数据库 |
| POST | `/api/init_db` | 初始化数据库 |
| GET | `/api/db_status` | 查询数据库状态 |
| GET | `/api/batches` | 获取批次列表 |
| GET | `/api/batch_items` | 获取批次数据 |
| POST | `/api/delete_batch` | 删除批次 |
| POST | `/api/export_csv` | 导出CSV |

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| V2.0.0 | 2026-05-01 | 新增数据分析模块（6维度可视化分析） |
| V1.0.0 | 2026-04-30 | 初始版本（爬虫采集与存储） |

## 注意事项

1. 请求间隔建议1-3秒，避免触发当当网反爬机制
2. 当当网页面编码为GBK，系统已自动处理编码检测
3. 数据库为可选项，不配置也可使用爬取和导出功能
4. `config.ini` 中包含数据库密码，请勿提交到公开仓库
5. 每页固定20本书，断点续爬据此计算已爬页数

## 许可证

© 2026 DangDang Crawler Project
