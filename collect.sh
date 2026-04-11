#!/bin/bash
# ~/devtrace/collect.sh
# 사용법:
#   collect.sh daily              → 오늘 것만
#   collect.sh full               → 전체 히스토리
#   collect.sh range DATE1 DATE2  → 날짜 범위
#   collect.sh project NAME       → 특정 프로젝트

source ~/devtrace/config.env

MODE="${1:-daily}"
TODAY=$(date +%Y-%m-%d)
TODAY_NUM=$(date +%Y%m%d)

# ─────────────────────────────────────
# 모드별 설정
# ─────────────────────────────────────
case "$MODE" in
    "daily")
        echo "📡 DevTrace 수집 시작: $TODAY"
        OUT_DIR="$LOG_DIR/$TODAY"
        DATE_FROM="$TODAY"
        DATE_TO="$TODAY"
        SEARCH_DIR="$PROJECT_DIR"
        ;;
    "full")
        echo "📚 전체 히스토리 수집 시작"
        OUT_DIR="$LOG_DIR/full"
        DATE_FROM=""
        DATE_TO=""
        SEARCH_DIR="$PROJECT_DIR"
        ;;
    "range")
        DATE_FROM="${2:-$TODAY}"
        DATE_TO="${3:-$TODAY}"
        echo "📅 날짜 범위 수집: $DATE_FROM ~ $DATE_TO"
        OUT_DIR="$LOG_DIR/range_${DATE_FROM}_${DATE_TO}"
        SEARCH_DIR="$PROJECT_DIR"
        ;;
    "project")
        PROJECT_NAME="${2:-}"
        if [ -z "$PROJECT_NAME" ]; then
            echo "❌ 프로젝트 이름을 입력하세요."
            exit 1
        fi
        # 홈 폴더 전체에서 프로젝트 폴더 검색
        FOUND=$(find "$PROJECT_DIR" -maxdepth 3 -type d -name "$PROJECT_NAME" 2>/dev/null | head -1)
        if [ -z "$FOUND" ]; then
            echo "❌ 프로젝트 폴더를 찾을 수 없습니다: $PROJECT_NAME"
            echo "   현재 인식된 프로젝트 목록:"
            find "$PROJECT_DIR" -maxdepth 2 -name ".git" -type d 2>/dev/null \
                | xargs -I{} dirname {} \
                | xargs -I{} basename {}
            exit 1
        fi
        echo "🔍 프로젝트 수집: $PROJECT_NAME ($FOUND)"
        OUT_DIR="$LOG_DIR/project_${PROJECT_NAME}"
        DATE_FROM=""
        DATE_TO=""
        SEARCH_DIR="$FOUND"
        ;;
esac

mkdir -p "$OUT_DIR"


# ─────────────────────────────────────
# 1. 터미널 히스토리 수집
# ─────────────────────────────────────
echo "[1/5] 터미널 히스토리 수집 중..."

history -a

if [ "$MODE" = "full" ] || [ "$MODE" = "project" ]; then
    cat ~/.bash_history > "$OUT_DIR/history.txt"

elif [ "$MODE" = "range" ]; then
    FROM_TS=$(date -d "$DATE_FROM 00:00:00" +%s 2>/dev/null)
    TO_TS=$(date -d "$DATE_TO 23:59:59" +%s 2>/dev/null)
    if grep -q "^#[0-9]" ~/.bash_history 2>/dev/null; then
        awk -v from="$FROM_TS" -v to="$TO_TS" '
            /^#[0-9]+/ { t = substr($0,2)+0; show=(t>=from && t<=to) }
            !/^#/ && show { print }
        ' ~/.bash_history > "$OUT_DIR/history.txt"
    else
        cat ~/.bash_history > "$OUT_DIR/history.txt"
    fi

else
    # daily
    if grep -q "^#[0-9]" ~/.bash_history 2>/dev/null; then
        TODAY_TIMESTAMP=$(date -d "$TODAY 00:00:00" +%s)
        awk -v ts="$TODAY_TIMESTAMP" '
            /^#[0-9]+/ { t = substr($0,2)+0; show=(t>=ts) }
            !/^#/ && show { print }
        ' ~/.bash_history > "$OUT_DIR/history.txt"
    else
        tail -200 ~/.bash_history > "$OUT_DIR/history.txt"
    fi
fi

echo "    → $(wc -l < "$OUT_DIR/history.txt")개 명령어 수집"


# ─────────────────────────────────────
# 2. 파일 변경 추적 (프로젝트별 분리)
# ─────────────────────────────────────
echo "[2/5] 파일 변경 내역 수집 중..."

if [ "$MODE" = "daily" ]; then
    MTIME_OPT="-mtime -1"
elif [ "$MODE" = "range" ]; then
    MTIME_OPT="-newermt $DATE_FROM ! -newermt $DATE_TO"
else
    MTIME_OPT=""
fi

# 전체 파일 목록
find "$SEARCH_DIR" \
    -type f \
    $MTIME_OPT \
    \( -name "*.py" -o -name "*.js" -o -name "*.jsx" \
       -o -name "*.ts" -o -name "*.tsx" -o -name "*.html" \
       -o -name "*.css" -o -name "*.sh" -o -name "*.java" \
       -o -name "*.c" -o -name "*.cpp" -o -name "*.go" \
       -o -name "*.rs" -o -name "*.vue" -o -name "*.rb" \) \
    ! -path "*/node_modules/*" \
    ! -path "*/.git/*" \
    ! -path "*/venv/*" \
    ! -path "*/devtrace/*" \
    -printf "%T+ %p\n" 2>/dev/null \
    | sort -r \
    > "$OUT_DIR/files.txt"

echo "    → $(wc -l < "$OUT_DIR/files.txt")개 파일 변경 감지"

# ─── 4번: 기술 스택 자동 감지 ───
echo "    → 기술 스택 감지 중..."
{
    echo "## 기술 스택 감지"
    declare -A tech_count
    while IFS= read -r line; do
        filepath=$(echo "$line" | awk '{print $2}')
        ext="${filepath##*.}"
        case "$ext" in
            py)      tech="Python" ;;
            js|jsx)  tech="JavaScript/React" ;;
            ts|tsx)  tech="TypeScript" ;;
            html)    tech="HTML" ;;
            css)     tech="CSS" ;;
            sh)      tech="Shell" ;;
            java)    tech="Java" ;;
            c|cpp)   tech="C/C++" ;;
            go)      tech="Go" ;;
            rs)      tech="Rust" ;;
            vue)     tech="Vue.js" ;;
            rb)      tech="Ruby" ;;
            *)       tech="기타" ;;
        esac
        tech_count[$tech]=$((${tech_count[$tech]:-0} + 1))
    done < "$OUT_DIR/files.txt"

    for tech in "${!tech_count[@]}"; do
        echo "  $tech: ${tech_count[$tech]}개 파일"
    done
} > "$OUT_DIR/tech_stack.txt"


# ─────────────────────────────────────
# 3. Git 로그 + Diff + 커밋 품질 체크
# ─────────────────────────────────────
echo "[3/5] Git 활동 수집 중..."

GIT_FILE="$OUT_DIR/git.txt"
DIFF_FILE="$OUT_DIR/diff.txt"
COMMIT_QUALITY_FILE="$OUT_DIR/commit_quality.txt"

echo "" > "$GIT_FILE"
echo "" > "$DIFF_FILE"
echo "## 커밋 메시지 품질 체크" > "$COMMIT_QUALITY_FILE"

find "$SEARCH_DIR" -name ".git" -type d ! -path "*/devtrace/*" 2>/dev/null | while read gitdir; do
    repo_dir=$(dirname "$gitdir")
    repo_name=$(basename "$repo_dir")

    # 커밋 로그
    if [ "$MODE" = "daily" ]; then
        commits=$(git -C "$repo_dir" log \
            --since="$TODAY 00:00:00" \
            --until="$TODAY 23:59:59" \
            --pretty=format:"[%h] %s (%ad)" \
            --date=format:"%H:%M" 2>/dev/null)
    elif [ "$MODE" = "range" ]; then
        commits=$(git -C "$repo_dir" log \
            --since="$DATE_FROM 00:00:00" \
            --until="$DATE_TO 23:59:59" \
            --pretty=format:"[%h] %s (%ad)" \
            --date=format:"%Y-%m-%d %H:%M" 2>/dev/null)
    else
        commits=$(git -C "$repo_dir" log \
            --pretty=format:"[%h] %s (%ad)" \
            --date=format:"%Y-%m-%d %H:%M" 2>/dev/null)
    fi

    if [ -n "$commits" ]; then
        echo "## 레포: $repo_name" >> "$GIT_FILE"
        echo "$commits" >> "$GIT_FILE"
        echo "" >> "$GIT_FILE"

        # git diff --stat (변경 줄 수)
        echo "## $repo_name 변경 통계" >> "$DIFF_FILE"
        git -C "$repo_dir" diff --stat HEAD~1 HEAD 2>/dev/null >> "$DIFF_FILE"
        echo "" >> "$DIFF_FILE"

        # ─── 5번: 커밋 메시지 품질 체크 ───
        echo "### $repo_name" >> "$COMMIT_QUALITY_FILE"
        git -C "$repo_dir" log --pretty=format:"%s" 2>/dev/null | while read msg; do
            msg_len=${#msg}
            if [ $msg_len -lt 10 ]; then
                echo "  ⚠️  너무 짧음: \"$msg\" (${msg_len}자)" >> "$COMMIT_QUALITY_FILE"
            elif echo "$msg" | grep -qiE "^(fix|update|test|wip|asdf|ㅁㄴㅇ|수정|변경)$"; then
                echo "  ⚠️  불명확: \"$msg\"" >> "$COMMIT_QUALITY_FILE"
            else
                echo "  ✅ 양호: \"$msg\"" >> "$COMMIT_QUALITY_FILE"
            fi
        done
        echo "" >> "$COMMIT_QUALITY_FILE"
    fi
done

echo "    → Git 로그 수집 완료"


# ─────────────────────────────────────
# 4. 에러 로그 + 패턴 분석
# ─────────────────────────────────────
echo "[4/5] 에러 로그 수집 중..."

ERROR_FILE="$OUT_DIR/errors.txt"

if [ "$MODE" = "daily" ]; then
    journalctl --since="$TODAY 00:00:00" \
        --until="$TODAY 23:59:59" \
        -p err --no-pager 2>/dev/null | tail -50 > "$ERROR_FILE"
elif [ "$MODE" = "range" ]; then
    journalctl --since="$DATE_FROM 00:00:00" \
        --until="$DATE_TO 23:59:59" \
        -p err --no-pager 2>/dev/null | tail -100 > "$ERROR_FILE"
else
    journalctl -p err --no-pager 2>/dev/null | tail -100 > "$ERROR_FILE"
fi

grep -i "error\|not found\|permission denied\|failed\|traceback\|exception" \
    "$OUT_DIR/history.txt" >> "$ERROR_FILE" 2>/dev/null

# ─── 1번: 에러 패턴 분석 (과거 에러와 비교) ───
echo "[5/5] 에러 패턴 분석 중..."

PATTERN_FILE="$OUT_DIR/error_patterns.txt"
echo "## 에러 패턴 분석" > "$PATTERN_FILE"

# 과거 에러 로그 전부 합치기
ALL_ERRORS_FILE="$LOG_DIR/all_errors_combined.txt"
find "$LOG_DIR" -name "errors.txt" ! -path "$OUT_DIR/*" 2>/dev/null \
    | xargs cat 2>/dev/null > "$ALL_ERRORS_FILE"

if [ -s "$ALL_ERRORS_FILE" ]; then
    echo "### 반복 에러 감지" >> "$PATTERN_FILE"
    # 현재 에러를 과거와 비교해서 반복되는 키워드 찾기
    grep -i "error\|failed\|not found" "$ERROR_FILE" 2>/dev/null | while read err_line; do
        keyword=$(echo "$err_line" | grep -oiE "[A-Za-z]+Error|[A-Za-z]+Exception|not found|permission denied" | head -1)
        if [ -n "$keyword" ]; then
            count=$(grep -ic "$keyword" "$ALL_ERRORS_FILE" 2>/dev/null || echo 0)
            if [ "$count" -gt 1 ]; then
                echo "  ⚠️  반복 에러: $keyword (과거 ${count}회 발생)" >> "$PATTERN_FILE"
            fi
        fi
    done
else
    echo "  (과거 에러 데이터 없음 - 데이터 쌓이면 패턴 분석 가능)" >> "$PATTERN_FILE"
fi

echo ""
echo "✅ 수집 완료!"
echo "   저장 위치: $OUT_DIR"
echo "   파일 목록: $(ls $OUT_DIR)"

