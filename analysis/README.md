# Analysis - 当当网畅销榜数据分析

独立于爬虫主项目的数据分析模块，支持按批次筛选不同时间段数据，提供6个维度的可视化分析。

## 目录结构

```
analysis/
├── README.md                           # 本文件
├── visualization.ipynb                 # Jupyter Notebook 分析代码
├── 当当网2025年畅销榜深度分析报告.md   # 完整分析报告（图文并茂）
└── charts/                             # 图表输出（按批次命名）
    ├── YR_bs_2025_01_分类势力范围.png
    ├── YR_bs_2025_02_价格排名关系.png
    ├── ...
    └── MO_bs_202601_01_分类势力范围.png
```

## 快速开始

### 1. 安装依赖

```bash
# 在项目根目录执行
uv pip install pandas numpy matplotlib seaborn squarify wordcloud jieba pymysql sqlalchemy
```

### 2. 确保数据就绪

先运行爬虫采集数据到MySQL数据库：

```bash
cd ..
uv run python main.py
```

### 3. 启动分析

```bash
# 方式一：Jupyter Notebook（推荐）
uv run jupyter notebook visualization.ipynb

# 方式二：命令行执行并导出HTML
uv run jupyter nbconvert --execute --to html visualization.ipynb
```

## 批次筛选（V2.1.0 新增）

数据库中存储了多个时间段的数据，通过 `batch_id` 字段区分。Notebook 启动后会自动列出所有可用批次：

```
可用批次列表:
  YR_bs_2025           | 500条 | bestseller  | 排名1-500
  MO_bs_202601         |  60条 | bestseller  | 排名1-60
```

### batch_id 编码规则

| 格式 | 示例 | 含义 |
|------|------|------|
| `YR_bs_{年份}` | `YR_bs_2025` | 年度畅销榜 |
| `MO_bs_{年月}` | `MO_bs_202601` | 月度畅销榜 |
| `YR_nw_{年份}` | `YR_nw_2025` | 年度新书热卖榜 |

### 切换分析批次

在 Notebook 的"批次选择"单元格中修改 `SELECTED_BATCH` 变量：

```python
# 分析2025年度畅销榜（默认）
SELECTED_BATCH = 'YR_bs_2025'

# 切换为2026年1月畅销榜
SELECTED_BATCH = 'MO_bs_202601'
```

图表文件会自动按批次命名，互不覆盖：

- `charts/YR_bs_2025_01_分类势力范围.png`
- `charts/MO_bs_202601_01_分类势力范围.png`

### 自适应分析

Notebook 会根据数据量自动调整：
- 排名分层：数据≤100条时分为3层，≤200条分为4层，>200条分为5层
- 出版社筛选：最低上榜数 = max(3, 数据量/100)
- 图表标题：自动显示当前批次的中文标签（如"2025年畅销榜"）

## 六个分析维度

| # | 图表 | 类型 | 分析目标 |
|:-:|------|------|---------|
| 1 | 分类势力范围 | 树状图 | 各分类市场份额 |
| 2 | 价格-排名关系 | 散点图 | 价格、评论数与排名关系 |
| 3 | 价格-评分组合 | 热力图 | 黄金定价与评分区间 |
| 4 | 标题关键词 | 词云图 | 畅销书流量密码 |
| 5 | 出版社实力 | 雷达图 | 头部出版社多维度对比 |
| 6 | 排名分层对比 | 箱线图 | 不同层级图书特征差异 |

## Notebook 结构

| 步骤 | 内容 |
|------|------|
| 第一步 | 环境配置（字体、配色、库导入） |
| 第二步 | 数据加载 + 批次列表展示 + 批次选择 |
| 第三步 | Top10畅销书预览（格式化表格） |
| 第四步 | 数据预处理（价格/评分/排名分层） |
| 图1-6 | 六个可视化分析 |
| 末尾 | 关键指标统计摘要 |

## 数据库配置

Notebook 从项目根目录的 `config.ini` 读取数据库连接信息，无硬编码密码：

```ini
[database]
host = localhost
port = 3306
username = root
password = 你的密码
database = dangdang_data
```

## 中文显示

Notebook 内置多策略中文字体查找：

1. 直接查找系统字体路径（Windows/macOS/Linux）
2. 扫描 `fontManager` 中的中文字体
3. 尝试常见字体名称

如仍无法显示中文，手动指定字体路径：

```python
import matplotlib.font_manager as fm
fm.fontManager.addfont(r'C:\Windows\Fonts\msyh.ttc')
```
