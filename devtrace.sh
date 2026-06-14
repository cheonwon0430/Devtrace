#!/bin/bash
# ~/devtrace/devtrace.sh

source ~/devtrace/config.env

TODAY=$(date +%Y-%m-%d)

echo "╔══════════════════════════════════╗"
echo "║         DevTrace v2.0            ║"
echo "║   개발 과정 자동 기록 시스템     ║"
echo "╚══════════════════════════════════╝"
echo ""

case "${1:-daily}" in

    "daily")
        echo "🗓  오늘($TODAY) 일지 생성 시작"
        bash ~/devtrace/collect.sh daily
        python3 ~/devtrace/analyze.py

        JOURNAL_FILE="$HOME/devtrace/journal/$TODAY.md"

        if [ -f "$JOURNAL_FILE" ] && [ -t 1 ]; then
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "✏️  [Human-in-the-Loop] AI가 일지를 생성했습니다."
            echo "   직접 검토하고 수정하시겠습니까? [Y/n]"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            read -r EDIT_CHOICE
            EDIT_CHOICE="${EDIT_CHOICE:-Y}"
            if [[ "$EDIT_CHOICE" =~ ^[Yy]$ ]]; then
                ${EDITOR:-nano} "$JOURNAL_FILE"
                echo "✅ 일지 저장 완료"
            else
                echo "⏭  편집 생략"
            fi

            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "📚 오늘 개발에 참고한 자료가 있나요? [y/N]"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            read -r REF_CHOICE
            REF_CHOICE="${REF_CHOICE:-N}"
            if [[ "$REF_CHOICE" =~ ^[Yy]$ ]]; then
                REF_DIR="$HOME/devtrace/references/$TODAY"
                mkdir -p "$REF_DIR"
                # 섹션 헤더 먼저 추가
                if ! grep -q "## 📚 참고 자료" "$JOURNAL_FILE"; then
                    echo "" >> "$JOURNAL_FILE"
                    echo "## 📚 참고 자료" >> "$JOURNAL_FILE"
                fi

                # 파일 선택 (여러 파일 한 번에)
                echo "   📂 파일 선택창을 열겠습니다. Ctrl+클릭으로 여러 파일 선택 가능합니다."
                REF_PATHS=$(zenity --file-selection \
                    --title="참고 자료 파일 선택 (Ctrl+클릭으로 다중 선택)" \
                    --filename="$HOME/" \
                    --multiple \
                    --separator=$'\n' \
                    2>/dev/null)
                if [ -n "$REF_PATHS" ]; then
                    while IFS= read -r REF_PATH; do
                        [ -z "$REF_PATH" ] && continue
                        if [ -f "$REF_PATH" ]; then
                            cp "$REF_PATH" "$REF_DIR/"
                            FNAME=$(basename "$REF_PATH")
                            echo "   ✅ 파일 저장됨: $FNAME"
                            echo "- 📄 $FNAME" >> "$JOURNAL_FILE"
                        fi
                    done <<< "$REF_PATHS"
                else
                    echo "   ⏭  파일 선택 생략"
                fi

                # URL 입력
                echo "   🌐 참고한 사이트 주소를 입력하세요."
                while true; do
                    REF_URL=$(zenity --entry \
                        --title="참고 사이트 URL 입력" \
                        --text="URL을 입력하세요 (취소하면 종료):" \
                        --entry-text="https://" \
                        2>/dev/null)
                    [ -z "$REF_URL" ] && break
                    echo "   ✅ URL 저장됨: $REF_URL"
                    echo "- 🌐 $REF_URL" >> "$JOURNAL_FILE"
                done
                echo "✅ 참고 자료 저장 완료: $REF_DIR"
            else
                echo "⏭  참고 자료 생략"
            fi
        fi

        echo ""
        echo "📖 일지 확인: $JOURNAL_FILE"
        ;;


    "full")
        echo "📚 전체 히스토리 요약 시작"
        bash ~/devtrace/collect.sh full
        python3 ~/devtrace/analyze.py full
        echo ""
        echo "📖 결과 확인: ~/devtrace/journal/full_summary.md"
        ;;

    "range")
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "❌ 사용법: devtrace.sh range 2026-04-01 2026-04-12"
            exit 1
        fi
        echo "📅 날짜 범위 분석: $2 ~ $3"
        bash ~/devtrace/collect.sh range "$2" "$3"
        python3 ~/devtrace/analyze.py range "$2" "$3"
        echo ""
        echo "📖 결과 확인: ~/devtrace/journal/range_${2}_${3}.md"
        ;;

    "project")
        if [ -z "$2" ]; then
            echo "❌ 사용법: devtrace.sh project 프로젝트이름"
            echo ""
            echo "📁 인식된 프로젝트 목록:"
            find "$PROJECT_DIR" -maxdepth 2 -name ".git" -type d 2>/dev/null \
                | xargs -I{} dirname {} \
                | xargs -I{} basename {}
            exit 1
        fi
        echo "🔍 프로젝트 분석: $2"
        bash ~/devtrace/collect.sh project "$2"
        python3 ~/devtrace/analyze.py project "$2"
        echo ""
        echo "📖 결과 확인: ~/devtrace/journal/project_${2}.md"
        ;;

    "regenerate")
        if [ -z "$2" ]; then
            echo "❌ 사용법: devtrace.sh regenerate 2026-04-12"
            exit 1
        fi
        echo "🔄 재생성: $2"
        python3 ~/devtrace/analyze.py regenerate "$2"
        ;;

    "weekly")
        echo "📊 주간 리포트 생성"
        python3 ~/devtrace/report.py weekly
        ;;

    "portfolio")
        if [ -z "$2" ]; then
            echo "❌ 사용법: devtrace.sh portfolio 프로젝트이름 [--template 템플릿이름]"
            echo ""
            echo "   사용 가능한 템플릿:"
            ls ~/devtrace/templates/ 2>/dev/null | sed 's/.md//' | sed 's/^/   - /'
            exit 1
        fi
        TEMPLATE="default"
        if [ "$3" = "--template" ] && [ -n "$4" ]; then
            TEMPLATE="$4"
        fi
        echo "🏗  포트폴리오 생성: $2 (템플릿: $TEMPLATE)"
        python3 ~/devtrace/report.py portfolio "$2" "$TEMPLATE"
        echo ""
        echo "📖 결과 확인: ~/devtrace/portfolio/${2}_README.md"
        ;;
        
    "push")
        echo "📤 GitHub push 중..."
        cd ~/devtrace
        git add -A 2>/dev/null
        git commit -m "devtrace: $(date +%Y-%m-%d) push" 2>/dev/null || true
        git push origin master 2>/dev/null && \
            echo "✅ GitHub push 완료" || \
            echo "⚠️  push 실패 (로컬에는 저장됨)"
        ;;

    "interview")
        if [ -z "$2" ]; then
            echo "❌ 사용법: devtrace.sh interview 프로젝트이름"
            exit 1
        fi
        echo "🎤 면접 질문 생성: $2"
        python3 ~/devtrace/report.py interview "$2"
        echo ""
        echo "📖 결과 확인: ~/devtrace/portfolio/${2}_interview.md"
        ;;

    "start")
        echo "👁  파일 감시 데몬 시작"
        bash ~/devtrace/daemon.sh
        ;;

    "stop")
        if [ -f /tmp/devtrace_daemon.pid ]; then
            kill $(cat /tmp/devtrace_daemon.pid)
            rm /tmp/devtrace_daemon.pid
            echo "✅ 데몬 종료"
        else
            echo "❌ 실행 중인 데몬 없음"
        fi
        ;;

    "status")
        if [ -f /tmp/devtrace_daemon.pid ]; then
            PID=$(cat /tmp/devtrace_daemon.pid)
            if kill -0 "$PID" 2>/dev/null; then
                echo "✅ 데몬 실행 중 (PID: $PID)"
            else
                echo "❌ 데몬 종료됨"
            fi
        else
            echo "❌ 데몬 실행 안 됨"
        fi
        echo ""
        echo "📚 저장된 일지 (최근 5개):"
        ls ~/devtrace/journal/*.md 2>/dev/null | tail -5
        ;;

    *)
        echo "사용법:"
        echo "  devtrace.sh daily                      → 오늘 일지 생성"
        echo "  devtrace.sh full                       → 전체 히스토리 요약"
        echo "  devtrace.sh range 2026-04-01 2026-04-12 → 날짜 범위 분석"
        echo "  devtrace.sh project 프로젝트이름       → 특정 프로젝트 분석"
        echo "  devtrace.sh regenerate 2026-04-12      → 일지 재생성"
        echo "  devtrace.sh weekly                     → 주간 리포트"
        echo "  devtrace.sh portfolio 프로젝트이름     → 포트폴리오 생성"
        echo "  devtrace.sh interview 프로젝트이름     → 면접 질문 생성"
        echo "  devtrace.sh start                      → 파일 감시 데몬 시작"
        echo "  devtrace.sh stop                       → 데몬 종료"
        echo "  devtrace.sh status                     → 상태 확인"
        echo "  devtrace.sh push                       → GitHub push"
        ;;
esac
