// 应用程序主要功能
class AINewsApp {
    constructor() {
        this.newsData = [];
        this.currentFilter = 'all';
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadNews();
    }

    bindEvents() {
        // 刷新按钮
        const refreshBtn = document.getElementById('refreshBtn');
        refreshBtn.addEventListener('click', () => {
            this.refreshNews();
        });

        // 分类过滤器
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('category-filter')) {
                this.handleCategoryFilter(e.target);
            }
        });

        // 新闻卡片点击事件
        document.addEventListener('click', (e) => {
            const newsCard = e.target.closest('.news-card');
            if (newsCard && !e.target.closest('.external-link')) {
                const articleId = newsCard.dataset.articleId;
                if (articleId) {
                    this.openArticleModal(articleId);
                }
            }
        });

        // 模态框背景点击关闭
        document.addEventListener('click', (e) => {
            if (e.target.id === 'articleModal') {
                this.closeModal();
            }
        });

        // ESC键关闭模态框
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }

    async loadNews() {
        try {
            this.showLoading();
            
            const response = await fetch('/api/news');
            const result = await response.json();
            
            if (result.success) {
                this.newsData = result.data;
                this.renderNews();
                this.updateTimestamp(result.timestamp);
                this.showCategoryFilter();
            } else {
                throw new Error(result.error || '获取数据失败');
            }
        } catch (error) {
            console.error('加载新闻失败:', error);
            this.showError(error.message);
        }
    }

    async refreshNews() {
        try {
            this.showLoading();
            
            const response = await fetch('/api/refresh');
            const result = await response.json();
            
            if (result.success) {
                this.newsData = result.data;
                this.renderNews();
                this.updateTimestamp(result.timestamp);
                this.showCategoryFilter();
                console.log('新闻数据已刷新');
            } else {
                throw new Error(result.error || '刷新数据失败');
            }
        } catch (error) {
            console.error('刷新新闻失败:', error);
            this.showError(error.message);
        }
    }

    showLoading() {
        document.getElementById('loadingState').classList.remove('hidden');
        document.getElementById('errorState').classList.add('hidden');
        document.getElementById('newsContainer').classList.add('hidden');
        document.getElementById('categoryFilter').classList.add('hidden');
        
        // 更新刷新按钮状态
        const refreshBtn = document.getElementById('refreshBtn');
        const icon = refreshBtn.querySelector('i');
        icon.classList.add('fa-spin');
        refreshBtn.disabled = true;
    }

    showError(message) {
        document.getElementById('loadingState').classList.add('hidden');
        document.getElementById('errorState').classList.remove('hidden');
        document.getElementById('newsContainer').classList.add('hidden');
        document.getElementById('categoryFilter').classList.add('hidden');
        
        document.getElementById('errorMessage').textContent = message;
        
        // 恢复刷新按钮状态
        this.resetRefreshButton();
    }

    resetRefreshButton() {
        const refreshBtn = document.getElementById('refreshBtn');
        const icon = refreshBtn.querySelector('i');
        icon.classList.remove('fa-spin');
        refreshBtn.disabled = false;
    }

    renderNews() {
        const container = document.getElementById('newsContainer').querySelector('.grid');
        
        // 过滤数据
        const filteredNews = this.currentFilter === 'all' 
            ? this.newsData 
            : this.newsData.filter(item => item.category === this.currentFilter);
        
        // 生成HTML
        container.innerHTML = filteredNews.map((item, index) => this.createNewsCard(item, index + 1)).join('');
        
        // 显示容器
        document.getElementById('loadingState').classList.add('hidden');
        document.getElementById('errorState').classList.add('hidden');
        document.getElementById('newsContainer').classList.remove('hidden');
        
        // 添加动画效果
        this.animateCards();
        
        // 恢复刷新按钮状态
        this.resetRefreshButton();
    }

    createNewsCard(item, articleId) {
        const sourceDisplay = item.source ? `<div class="text-xs text-gray-500 mb-2">
            <i class="fas fa-newspaper mr-1"></i>
            <span>${item.source}</span>
        </div>` : '';
        return `
            <div class="news-card fade-in cursor-pointer hover:shadow-lg transition-all duration-200" data-article-id="${articleId}">
                <div class="news-card-header">
                    <div class="flex justify-between items-start mb-3">
                        <span class="category-badge category-${item.category}">
                            ${this.getCategoryIcon(item.category)} ${item.category}
                        </span>
                        <div class="text-xs text-gray-400">
                            <i class="fas fa-arrow-right"></i>
                        </div>
                    </div>
                    ${sourceDisplay}
                    <h3 class="news-title hover:text-blue-600 transition-colors duration-200">${item.title}</h3>
                </div>
                <div class="news-card-body">
                    <p class="news-summary">${item.ai_summary || item.summary}</p>
                </div>
                <div class="news-card-footer">
                    <div class="news-time">
                        <i class="fas fa-clock mr-2"></i>
                        ${item.time}
                    </div>
                    <div class="text-xs text-gray-400">
                        点击查看详情
                    </div>
                </div>
            </div>
        `;
    }

    openArticleModal(articleId) {
        const article = this.newsData[articleId - 1];
        if (!article) {
            console.error('文章不存在:', articleId);
            return;
        }

        // 填充模态框内容
        document.getElementById('modalTitle').textContent = article.title;
        document.getElementById('modalTime').textContent = article.time;
        document.getElementById('modalSource').textContent = article.source || '未知来源';
        document.getElementById('modalCategory').textContent = article.category;
        document.getElementById('modalSummary').textContent = article.ai_summary || article.summary;
        
        // 设置原文链接
        const modalLink = document.getElementById('modalLink');
        if (article.url) {
            modalLink.href = article.url;
            modalLink.classList.remove('hidden');
        } else {
            modalLink.classList.add('hidden');
        }

        // 显示模态框
        document.getElementById('articleModal').classList.remove('hidden');
        document.body.style.overflow = 'hidden'; // 防止背景滚动
    }

    closeModal() {
        document.getElementById('articleModal').classList.add('hidden');
        document.body.style.overflow = ''; // 恢复背景滚动
    }

    handleCategoryFilter(button) {
        // 移除所有active类
        document.querySelectorAll('.category-filter').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // 添加active类到当前按钮
        button.classList.add('active');
        
        // 更新当前过滤器
        this.currentFilter = button.dataset.category;
        
        // 重新渲染新闻
        this.renderNews();
    }

    getCategoryIcon(category) {
        // 返回空字符串，不显示图标，只显示中文分类名称
        return '';
    }

    showCategoryFilter() {
        if (this.newsData.length > 0) {
            document.getElementById('categoryFilter').classList.remove('hidden');
        }
    }

    updateTimestamp(timestamp) {
        const updateTimeElement = document.getElementById('updateTime');
        if (timestamp) {
            const date = new Date(timestamp);
            updateTimeElement.textContent = date.toLocaleString('zh-CN');
        } else {
            updateTimeElement.textContent = new Date().toLocaleString('zh-CN');
        }
    }

    animateCards() {
        const cards = document.querySelectorAll('.news-card');
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
        });
    }
}

// 全局函数
function loadNews() {
    if (window.newsApp) {
        window.newsApp.loadNews();
    }
}

function closeModal() {
    if (window.newsApp) {
        window.newsApp.closeModal();
    }
}

// 工具函数
const utils = {
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    },

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            console.log('文本已复制到剪贴板');
        }).catch(err => {
            console.error('复制失败:', err);
        });
    }
};

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.newsApp = new AINewsApp();
});

// 错误处理
window.addEventListener('error', (e) => {
    console.error('全局错误:', e.error);
});

window.addEventListener('unhandledrejection', (e) => {
    console.error('未处理的Promise拒绝:', e.reason);
}); 