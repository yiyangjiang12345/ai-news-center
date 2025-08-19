from flask import Flask, render_template, jsonify, request, abort, Response
from flask_cors import CORS
import requests
import json
from datetime import datetime, timedelta
import math
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
import os
from dotenv import load_dotenv
import threading
import time
from queue import Queue

# 加载环境变量
load_dotenv()

app = Flask(__name__)
CORS(app)

# 全局变量存储文章数据
articles_cache = {}
current_articles = []
_sse_listeners = set()

def _sse_notify(event_type: str, payload: dict):
    try:
        message = {"type": event_type, **payload}
        for q in list(_sse_listeners):
            try:
                q.put_nowait(message)
            except Exception:
                pass
    except Exception:
        pass

# 配置博查AI API（不提供默认值，避免泄露）
BOCHA_API_KEY = os.getenv('BOCHA_API_KEY')

# 配置火山引擎 API（不提供默认值，避免泄露）
VOLCENGINE_API_KEY = os.getenv("VOLCENGINE_API_KEY")
VOLCENGINE_ENDPOINT_ID = os.getenv("VOLCENGINE_ENDPOINT_ID")

# 初始化火山引擎客户端
try:
    from volcengine.ark import Ark
    client = Ark(api_key=VOLCENGINE_API_KEY)
    print(f"火山引擎客户端初始化成功，使用端点: {VOLCENGINE_ENDPOINT_ID}")
except ImportError:
    try:
        from volcenginesdkarkruntime import Ark
        client = Ark(api_key=VOLCENGINE_API_KEY)
        print(f"火山引擎客户端初始化成功，使用端点: {VOLCENGINE_ENDPOINT_ID}")
    except ImportError:
        client = None
        print("未检测到可用的火山引擎SDK，请检查依赖安装")
except Exception as e:
    print(f"火山引擎客户端初始化失败: {e}")
    client = None

class BochaNewsService:
    def __init__(self):
        self.api_key = BOCHA_API_KEY
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        # 后台刷新配置（起始时间与间隔小时），通过环境变量设置
        # 支持三种方式：
        # 1) NEWS_REFRESH_START_TIME=HH:MM（优先）
        # 2) NEWS_REFRESH_START_HOUR、NEWS_REFRESH_START_MINUTE
        # 3) 若未配置分钟则按 00 分钟
        self.refresh_start_hour = self._parse_int(os.getenv('NEWS_REFRESH_START_HOUR', '0'), 0)
        self.refresh_start_minute = self._parse_int(os.getenv('NEWS_REFRESH_START_MINUTE', '0'), 0)
        start_time_str = os.getenv('NEWS_REFRESH_START_TIME')
        if start_time_str and ':' in start_time_str:
            parts = start_time_str.split(':', 1)
            self.refresh_start_hour = self._parse_int(parts[0], self.refresh_start_hour)
            self.refresh_start_minute = self._parse_int(parts[1], self.refresh_start_minute)
        # 合法性校验
        if self.refresh_start_hour < 0 or self.refresh_start_hour > 23:
            self.refresh_start_hour = 0
        if self.refresh_start_minute < 0 or self.refresh_start_minute > 59:
            self.refresh_start_minute = 0
        self.refresh_interval_hours = max(1, self._parse_int(os.getenv('NEWS_REFRESH_INTERVAL_HOURS', '4'), 4))
        # 时区（可选）。例如：Asia/Shanghai、UTC
        self.refresh_tz_name = os.getenv('NEWS_REFRESH_TZ')
        self.refresh_tz = None
        if self.refresh_tz_name and ZoneInfo is not None:
            try:
                self.refresh_tz = ZoneInfo(self.refresh_tz_name)
            except Exception:
                self.refresh_tz = None
    
    # ==== 时间工具：按照配置时区返回当前时间 ====
    def _now_dt(self):
        return datetime.now(self.refresh_tz) if self.refresh_tz else datetime.now()

    def _now_str(self):
        return self._now_dt().strftime('%Y-%m-%d %H:%M:%S')
    
    def get_ai_news(self, force_refresh=False):
        """获取今日AI咨询"""
        global current_articles
        
        try:
            print("正在调用博查AI API获取AI新闻...")
            current_date = self._now_dt().strftime("%Y-%m-%d")
            
            # 使用include参数指定搜索网站范围
            include_sites = "sohu.com|news.ifeng.com|36kr.com|techcrunch.com|venturebeat.com|theverge.com|arstechnica.com|zdnet.com"
            exclude_sites = "tech.gmw.cn|m.gmw.cn"
            # 构建查询
            query = f"全球范围内关于AI人工智能的最新动态新闻，重点关注具有行业影响力的技术突破、产品发布、行业趋势、投资融资和政策法规等方面的内容"
            
            print(f"执行查询: {query}")
            
            # 调用博查Web Search API
            url = 'https://api.bochaai.com/v1/web-search'
            data = {
                "query": query,
                "freshness": "oneDay",
                "summary": True,
                "count": 50,
                "exclude_sites": exclude_sites
            }
            
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                news_data = self.parse_bocha_response(result)
                if news_data and len(news_data) > 0:
                    current_articles = news_data
                    self.update_articles_cache(news_data)
                    print(f"API调用成功，返回 {len(news_data)} 条新闻数据")
                    _sse_notify("news_updated", {"last_update": self._now_str(), "count": len(news_data)})
                    return news_data
                else:
                    print("API调用成功但未获取到有效新闻数据")
                    current_articles = []
                    self.update_articles_cache([])
                    return []
            else:
                print(f"API调用失败: {response.status_code}")
                current_articles = []
                return []
                
        except Exception as e:
            print(f"API调用失败: {e}")
            current_articles = []
            return []
    
    def parse_bocha_response(self, api_response):
        """批量用火山引擎处理所有新闻，筛选、提炼、生成结构化AI新闻"""
        try:
            print(f"开始解析API响应，响应类型: {type(api_response)}")
            if 'data' in api_response and 'webPages' in api_response['data']:
                webpages = api_response['data']['webPages']['value']
                print(f"找到webPages数据，包含{len(webpages)}个项目")
                
                # 1. 拼接所有原始新闻内容
                all_raw_news = []
                for i, page in enumerate(webpages):
                    title = page.get('name', '')
                    summary = page.get('summary', '')
                    all_raw_news.append(f"原始内容{i+1}：\n标题：{title}\n内容：{summary}")
                all_raw_text = '\n\n'.join(all_raw_news)
                
                # 2. 一次性调用火山引擎
                if client:
                    system_prompt = (
                        "你是一个专业的AI新闻编辑，负责对AI相关新闻进行筛选、提炼和专业化加工。"
                        "请根据以下原始新闻内容，筛选出与AI相关且有价值的新闻，去除无关内容。"
                        "每条新闻请根据其摘要内容自动生成一个吸引人且与AI强相关的标题（不要直接使用原文标题），让用户一看就知道和AI有关并有兴趣点击。"
                        "摘要部分请对原文summary进行总结和概括。"
                        "每条新闻请严格输出如下格式："
                        "原始序号：[数字]"
                        "标题：[自动生成的AI相关标题]"
                        "摘要：[对summary的总结概括]"
                        "分类：[技术突破/产品发布/行业动态/投资融资/政策法规]"
                        "请输出多条新闻时，每条新闻之间用两个换行分隔。"
                    )
                    user_prompt = (
                        f"请根据以下原始新闻内容，筛选、提炼并生成结构化AI新闻，去除无关内容。\n\n"
                        f"{all_raw_text}\n\n"
                        f"请严格按照如下格式输出：\n"
                        f"原始序号：[数字]\n标题：[自动生成的AI相关标题]\n摘要：[对summary的总结概括]\n分类：[技术突破/产品发布/行业动态/投资融资/政策法规]"
                        f"\n多条新闻之间用两个换行分隔。"
                    )
                    print("批量调用火山引擎...输入内容长度:", len(all_raw_text))
                    volcengine_result = self.generate_with_volcengine_batch(system_prompt, user_prompt)
                    print("火山引擎批量返回：", volcengine_result[:500])
                    # 3. 解析火山引擎返回的多条新闻
                    news_list = self.parse_volcengine_batch_response(volcengine_result, webpages)
                    print(f"批量解析后news_list长度: {len(news_list)}")
                    for idx, item in enumerate(news_list):
                        print(f"news_list[{idx}]: {item}")
                    return news_list
                else:
                    print("未检测到火山引擎SDK，直接返回原始新闻")
                    # 兼容：直接返回原始新闻
                    news_list = []
                    current_time = self._now_dt()
                    for i, page in enumerate(webpages):
                        news_item = {
                            'id': str(i + 1),
                            'title': page.get('name', ''),
                            'url': page.get('url', ''),
                            'summary': page.get('summary', ''),
                            'source': page.get('siteName', '未知来源'),
                            'time': current_time.strftime('%Y-%m-%d %H:%M'),
                            'category': '技术突破',
                            'created_at': current_time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                        news_list.append(news_item)
                    return news_list
            else:
                print("API响应格式不符合预期")
                return []
        except Exception as e:
            print(f"解析响应失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def generate_with_volcengine_batch(self, system_prompt, user_prompt):
        """批量调用火山引擎"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=VOLCENGINE_ENDPOINT_ID,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    stream=False
                )
                if response and hasattr(response, 'choices') and response.choices:
                    return response.choices[0].message.content
            except Exception as e:
                print(f"火山引擎批量API调用失败 (尝试 {attempt + 1}/3): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        return ""

    def parse_volcengine_batch_response(self, response_text, webpages):
        """解析火山引擎批量返回的多条新闻，返回新闻列表，优先用原始序号匹配url/source"""
        if not response_text:
            return []
        import re
        blocks = [b.strip() for b in response_text.strip().split('\n\n') if b.strip()]
        news_list = []
        current_time = self._now_dt()
        for idx, block in enumerate(blocks):
            title, summary, category, raw_index = None, None, None, None
            for line in block.split('\n'):
                line = line.strip()
                if line.startswith('原始序号：') or line.startswith('原始序号:'):
                    raw_index = re.sub(r'[^0-9]', '', line)
                elif line.startswith('标题：') or line.startswith('标题:'):
                    title = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                elif line.startswith('摘要：') or line.startswith('摘要:'):
                    summary = line.split('：', 1)[-1].split(':', 1)[-1].strip()
                elif line.startswith('分类：') or line.startswith('分类:'):
                    category = line.split('：', 1)[-1].split(':', 1)[-1].strip()
            # 去除分类中括号
            if category:
                category = category.strip('[]').strip()
            # 优先用原始序号匹配url/source
            url = ''
            source = ''
            if raw_index and raw_index.isdigit():
                idx0 = int(raw_index) - 1
                if 0 <= idx0 < len(webpages):
                    url = webpages[idx0].get('url', '')
                    source = webpages[idx0].get('siteName', '未知来源')
            # 兼容：如果没有原始序号，尝试用标题模糊匹配
            if not url:
                for page in webpages:
                    if title and title in page.get('name', ''):
                        url = page.get('url', '')
                        source = page.get('siteName', '未知来源')
                        break
            news_item = {
                'id': str(idx + 1),
                'title': title or '',
                'url': url,
                'summary': summary or '',
                'source': source,
                'time': current_time.strftime('%Y-%m-%d %H:%M'),
                'category': category or '技术突破',
                'created_at': current_time.strftime('%Y-%m-%d %H:%M:%S')
            }
            news_list.append(news_item)
        return news_list
    
    # 已移除未使用的工具方法：clean_summary / deduplicate_news / categorize_news
    
    def update_articles_cache(self, articles):
        """更新文章缓存"""
        global articles_cache
        articles_cache.clear()
        for article in articles:
            articles_cache[article['id']] = article
    
    def start_background_refresh(self):
        """启动后台刷新任务"""
        refresh_thread = threading.Thread(target=self._background_refresh_worker, daemon=True)
        refresh_thread.start()
        print(
            f"后台刷新任务已启动：起始时间={str(self.refresh_start_hour).zfill(2)}:"
            f"{str(self.refresh_start_minute).zfill(2)}，间隔={self.refresh_interval_hours} 小时"
        )
    
    def _background_refresh_worker(self):
        """后台刷新工作线程（按起始点与间隔调度）"""
        while True:
            try:
                # 计算距离下一次刷新时间
                sleep_seconds = self._seconds_until_next_refresh()
                hours_left = max(0.0, sleep_seconds / 3600.0)
                print(f"后台刷新：距离下一次刷新约 {hours_left:.2f} 小时")
                time.sleep(sleep_seconds)
                print("执行后台刷新...")
                self.get_ai_news()
            except Exception as e:
                print(f"后台刷新任务错误: {e}")
                time.sleep(60)

    def _seconds_until_next_refresh(self) -> int:
        """计算距离下一次刷新的秒数。按每日 refresh_start_hour 为基点，每隔 refresh_interval_hours 小时一次。"""
        now = datetime.now(self.refresh_tz) if self.refresh_tz else datetime.now()
        today_base = now.replace(
            hour=self.refresh_start_hour,
            minute=self.refresh_start_minute,
            second=0,
            microsecond=0
        )
        interval_sec = max(1, int(self.refresh_interval_hours * 3600))

        if now <= today_base:
            next_time = today_base
        else:
            elapsed = (now - today_base).total_seconds()
            cycles = math.ceil(elapsed / interval_sec)
            next_time = today_base + timedelta(seconds=cycles * interval_sec)

        # 最小睡眠 60 秒，避免频繁循环
        sleep_seconds = int(max(60, (next_time - now).total_seconds()))
        return sleep_seconds

    @staticmethod
    def _parse_int(value: str, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def generate_with_volcengine(self, context):
        """使用火山引擎对内容进行二次加工"""
        if not VOLCENGINE_API_KEY:
            print("未设置 VOLCENGINE_API_KEY 环境变量")
            return self.simple_text_processing(context)

        system_prompt = (
            "你是一个专业的AI新闻编辑，负责对AI相关的新闻内容进行二次加工。"
            "你需要从原始内容中提取关键信息，生成简洁明了的标题、摘要和分类。"
            "要求："
            "1. 标题要简洁有力，突出AI技术或产品的核心信息"
            "2. 摘要要包含主要事实、技术特点、影响等关键信息"
            "3. 语言要通俗易懂，避免过于技术化的术语"
            "4. 保持客观中立的语调"
            "5. 分类必须从以下5个选项中选择一个："
            "   - 技术突破：新的AI技术、算法、研究成果等"
            "   - 产品发布：新产品、新功能、版本更新等"
            "   - 行业动态：公司合作、并购、市场变化等"
            "   - 投资融资：融资、投资、上市等商业活动"
            "   - 政策法规：政府政策、法规、监管等"
            "6. 必须严格按照以下格式返回，不要添加其他内容："
            "   标题：[生成的标题]"
            "   摘要：[生成的摘要]"
            "   分类：[生成的分类]"
        )

        user_prompt = (
            f"请对以下AI相关新闻内容进行二次加工，生成标题、摘要和分类：\n\n"
            f"原始内容：{context}\n\n"
            f"请严格按照以下格式返回（不要添加其他内容）：\n"
            f"标题：[生成的标题]\n"
            f"摘要：[生成的摘要]\n"
            f"分类：[技术突破/产品发布/行业动态/投资融资/政策法规]"
        )

        # 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"火山引擎API调用尝试 {attempt + 1}/{max_retries}")
                response = client.chat.completions.create(
                    model=VOLCENGINE_ENDPOINT_ID,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    stream=False
                )
                
                if response and hasattr(response, 'choices') and response.choices:
                    result = response.choices[0].message.content
                    print(f"火山引擎API调用成功，响应长度: {len(result)}")
                    return result
                else:
                    print(f"火山引擎API响应格式异常: {response}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # 指数退避
                        continue
                    
            except Exception as e:
                print(f"火山引擎 API 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                    continue
                else:
                    print(f"所有重试都失败了，使用简化处理")
                    break
        
        print(f"上下文长度: {len(context)}")
        return self.simple_text_processing(context)

    def simple_text_processing(self, context):
        """简化的文本处理逻辑，用于替代火山引擎"""
        try:
            # 简单的文本清理和优化
            lines = context.split('\n')
            title = ""
            summary = ""
            
            # 提取标题（通常是第一行或包含"标题"的行）
            for line in lines:
                line = line.strip()
                if line and len(line) > 5:
                    if "标题" in line:
                        title = line.replace("标题:", "").replace("标题：", "").strip()
                        break
                    elif not title and len(line) < 100:
                        title = line
                        break
            
            # 如果没有找到合适的标题，使用默认标题
            if not title:
                title = "AI行业最新动态"
            
            # 提取摘要（去除重复内容，保留关键信息）
            content_lines = []
            seen_lines = set()
            
            for line in lines:
                line = line.strip()
                if line and len(line) > 10 and line not in seen_lines:
                    seen_lines.add(line)
                    content_lines.append(line)
            
            # 组合摘要
            summary = " ".join(content_lines[:3])  # 只保留前3行
            if len(summary) > 200:
                summary = summary[:200] + "..."
            
            if not summary:
                summary = "暂无详细摘要"
            
            # 使用默认分类，因为火山引擎不可用时无法进行智能分类
            category = "技术突破"
            
            return f"标题：{title}\n摘要：{summary}\n分类：{category}"
            
        except Exception as e:
            print(f"简化文本处理失败: {e}")
            return None

    # 已移除未使用的解析方法：parse_volcengine_response

# 初始化服务
bocha_service = BochaNewsService()

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/article/<article_id>')
def article_detail(article_id):
    """文章详情页"""
    article = articles_cache.get(article_id)
    if not article:
        abort(404)
    return render_template('article.html', article=article)

@app.route('/api/news')
def get_news():
    """获取新闻列表API"""
    try:
        if not current_articles:
            # 如果没有缓存数据，获取新数据
            bocha_service.get_ai_news()
        
        return jsonify({
            'success': True,
            'data': current_articles,
            'count': len(current_articles),
            'last_update': bocha_service._now_str()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/refresh')
def refresh_news():
    """刷新新闻API"""
    try:
        news_data = bocha_service.get_ai_news(force_refresh=True)
        return jsonify({
            'success': True,
            'data': news_data,
            'count': len(news_data),
            'last_update': bocha_service._now_str()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/article/<article_id>')
def get_article(article_id):
    """获取单篇文章详情API"""
    try:
        article = articles_cache.get(article_id)
        if not article:
            return jsonify({
                'success': False,
                'error': '文章不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': article
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/related-articles/<article_id>')
def get_related_articles(article_id):
    """获取相关文章API"""
    try:
        current_article = articles_cache.get(article_id)
        if not current_article:
            return jsonify({
                'success': False,
                'error': '文章不存在'
            }), 404
        
        # 简单的相关文章推荐：基于分类
        related_articles = []
        current_category = current_article.get('category', '')
        
        for aid, article in articles_cache.items():
            if aid != article_id and article.get('category') == current_category:
                related_articles.append(article)
                if len(related_articles) >= 3:  # 最多返回3篇相关文章
                    break
        
        return jsonify({
            'success': True,
            'data': related_articles
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return render_template('404.html'), 404

@app.route('/api/stream')
def stream():
    """服务端事件流（SSE）：后端刷新后立即通知前端。"""
    def event_stream():
        q = Queue(maxsize=10)
        _sse_listeners.add(q)
        # 连接建立时发送一次心跳
        yield f"data: {json.dumps({'type':'heartbeat','ts': bocha_service._now_str()})}\n\n"
        try:
            while True:
                msg = q.get()
                yield f"data: {json.dumps(msg)}\n\n"
        except GeneratorExit:
            pass
        finally:
            try:
                _sse_listeners.discard(q)
            except Exception:
                pass
    headers = {
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    }
    return Response(event_stream(), mimetype='text/event-stream', headers=headers)

if __name__ == '__main__':
    # 启动后台刷新任务
    bocha_service.start_background_refresh()
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True) 