# AI新闻聚合网站

这是一个基于 Flask 的 AI 新闻聚合网站，使用 Bocha AI 搜索（支持 `web-search`/`ai-search`），并可选接入火山引擎进行内容二次加工。已内置 SSE 实时通知，后端刷新后前端会立即拉取最新内容。

## 功能特点

- 🔍 **智能新闻搜索**: 使用 Bocha AI Search API 获取资讯（可配置端点）
- 🎯 **定向搜索**: 可配置 include/exclude 站点范围
- 🤖 **AI内容优化（可选）**: 接入火山引擎 Ark 进行批量加工
- 📱 **响应式设计**: 现代化的Web界面，支持移动端
- ⚡ **实时更新**: 自动定时更新新闻内容

## 技术栈

- **后端**: Flask + Python
- **AI 搜索**: Bocha AI Search API（`BOCHA_API_URL` 可切换 `web-search`/`ai-search`）
- **内容优化**: 火山引擎 Ark（可选）
- **前端**: HTML5 + CSS3 + JavaScript（SSE + 轮询兜底）
- **部署**: Gunicorn

## 环境要求

- Python 3.9+
- Bocha AI API 密钥（必填）
- 火山引擎 API 密钥与端点（可选）

## 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd project
   ```

2. **创建虚拟环境**
   ```bash
   python -m venv ai_news_env
   source ai_news_env/bin/activate  # Linux/Mac
   # 或
   ai_news_env\Scripts\activate  # Windows
   ```

3. **安装依赖**（已精简冲突依赖）
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**（`start.sh` 首次会生成 `.env` 模版）
   创建 `.env` 文件并添加以下配置：
   ```env
   # Bocha
   BOCHA_API_KEY=your_bocha_api_key
   # 可切换 web-search / ai-search
   BOCHA_API_URL=https://api.bochaai.com/v1/ai-search

   # Volcengine (optional)
   VOLCENGINE_API_KEY=your_volcengine_api_key
   VOLCENGINE_ENDPOINT_ID=your_endpoint_id

   # 后台刷新调度与时区
   # 方式一（优先）：每日起始时间
   NEWS_REFRESH_START_TIME=11:20
   # 方式二：起始小时/分钟（0-23 / 0-59）
   # NEWS_REFRESH_START_HOUR=11
   # NEWS_REFRESH_START_MINUTE=20
   # 刷新间隔（小时，>=1）
   NEWS_REFRESH_INTERVAL_HOURS=4
   # 时区（示例：Asia/Shanghai / UTC）
   NEWS_REFRESH_TZ=Asia/Shanghai
   ```

## 运行项目

### 方法1: 使用提供的脚本（推荐）
```bash
chmod +x start.sh
./start.sh
```

### 方法2: 手动运行
```bash
# 激活虚拟环境
source ai_news_env/bin/activate

# 运行Flask应用
python app.py
```

### 方法3: 使用 Gunicorn（生产环境，可选）
```bash
source ai_news_env/bin/activate
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 配置说明

### 火山引擎配置（可选）
- `VOLCENGINE_API_KEY`: 火山引擎 API 密钥
- `VOLCENGINE_ENDPOINT_ID`: Ark 模型端点ID

### Bocha AI 配置
- `BOCHA_API_KEY`: Bocha AI API 密钥
- `BOCHA_API_URL`: `https://api.bochaai.com/v1/web-search` 或 `https://api.bochaai.com/v1/ai-search`

### 搜索与刷新配置
- 默认搜索领域：AI 行业资讯（在后端可改查询词/站点范围）
- 更新策略：
  - 后端按 `.env` 设定的起始时间与间隔自动刷新（含时区）
  - 前端通过 SSE 自动接收“刷新完成”事件并立即拉取最新数据
  - 轮询兜底：默认 60 分钟，可用 `?poll=15` 或 `localStorage.setItem('poll_minutes','15')` 覆盖

刷新按钮说明（默认“假刷新”）：
- 用户点击后显示加载 10 秒，不打后端；结束后轻微调整列表顺序并更新时间，营造刷新感；
- 开发者真实刷新开关：
  - 控制台：`localStorage.setItem('dev_real_refresh','1'); location.reload();`
  - 或 URL：在地址后加 `?dev=1`

## 项目结构

```
project/
├── app.py              # 主应用文件
├── config.py           # （已移除：配置改用 .env 与环境变量）
├── requirements.txt    # Python依赖
├── run.sh             # 运行脚本
├── static/            # 静态文件
│   ├── css/
│   └── js/
└── templates/         # HTML模板
    ├── index.html
    ├── article.html
    └── 404.html
```

## API接口

### 获取新闻列表
```
GET /api/news
```

### 获取单篇新闻详情
```
GET /api/news/<int:news_id>
```

## 故障排除

### 1. 火山引擎API错误
- 检查API密钥是否正确
- 确认端点ID是否有效
- 查看网络连接是否正常

### 2. Bocha AI搜索失败
- 验证API密钥
- 检查搜索关键词设置
- 确认目标网站可访问

### 3. 依赖安装问题
```bash
# 重新安装依赖
pip uninstall -r requirements.txt
pip install -r requirements.txt
```

## 开发说明

### 添加新的搜索源
在 `BochaNewsService` 类中修改 `search_news` 方法的 `include` 参数。

### 修改AI处理逻辑
在 `generate_with_volcengine` 方法中调整系统提示词和用户提示词。

### 自定义样式
修改 `static/css/style.css` 文件来自定义界面样式。

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！ 