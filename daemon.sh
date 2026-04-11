#!/bin/bash
# ~/devtrace/daemon.sh
# 역할: 백그라운드에서 파일 변경을 실시간 감지

source ~/devtrace/config.env

WATCH_LOG="$LOG_DIR/inotify_$(date +%Y%m%d).txt"

echo "👁  DevTrace 데몬 시작 (프로젝트 폴더: $PROJECT_DIR)"
echo "   로그 파일: $WATCH_LOG"

inotifywait \
    -m -r \
    -e modify,create,delete,moved_to \
    --format '%T | %e | %w%f' \
    --timefmt '%Y-%m-%d %H:%M:%S' \
    --exclude '(node_modules|\.git|venv|__pycache__|\.pyc)' \
    "$PROJECT_DIR" \
    2>/dev/null \
    >> "$WATCH_LOG" &

DAEMON_PID=$!
echo $DAEMON_PID > /tmp/devtrace_daemon.pid
echo "   데몬 PID: $DAEMON_PID"
echo "   종료하려면: kill $DAEMON_PID"

