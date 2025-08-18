#!/bin/bash

# 停止AI新闻网站脚本
echo "正在停止AI新闻网站..."

# 查找并杀死Python进程
pids=$(ps aux | grep "python app.py" | grep -v grep | awk '{print $2}')

if [ -z "$pids" ]; then
    echo "未找到运行中的AI新闻网站进程"
else
    echo "找到进程: $pids"
    for pid in $pids; do
        echo "停止进程 $pid..."
        kill $pid
    done
    echo "AI新闻网站已停止"
fi 