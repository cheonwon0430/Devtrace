#!/usr/bin/env python3
# ~/devtrace/analyze.py
# 사용법:
#   analyze.py                        → 오늘 일지
#   analyze.py 2026-04-12             → 특정 날짜
#   analyze.py full                   → 전체 히스토리
#   analyze.py range 2026-04-01 2026-04-12
#   analyze.py project myproject
#   analyze.py regenerate 2026-04-12  → 재생성

import os
import sys
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path.home() / "devtrace" / "config.env")

API_KEY = os.getenv("GROQ_API_KEY")
LOG_DIR = Path(os.getenv("LOG_DIR", str(Path.home() / "devtrace/logs")))
JOURNAL_DIR = Path(os.getenv("JOURNAL_DIR", str(Path.home() / "devtrace/journal")))

JOURNAL_DIR.mkdir(parents=True, exist_ok=True)


def read_file(path: Path) -> str:
    if path.exists():
        content = path.read_text(encoding="utf-8", errors="ignore").strip()
        return content if content else "(없음)"
    return "(없음)"


def load_logs(log_subdir: Path) -> dict:
    return {
        "history":        read_file(log_subdir / "history.txt"),
        "files":          read_file(log_subdir / "files.txt"),
        "git":            read_file(log_subdir / "git.txt"),
        "diff":           read_file(log_subdir / "diff.txt"),
        "errors":         read_file(log_subdir / "errors.txt"),
        "tech_stack":     read_file(log_subdir / "tech_stack.txt"),
        "commit_quality": read_file(log_subdir / "commit_quality.txt"),
        "error_patterns": read_file(log_subdir / "error_patterns.txt"),
    }


def build_prompt(mode: str, logs: dict, label: str = "") -> str:

    # 공통 로그 블록
    log_block = f"""
### 터미널 히스토리
{logs['history'][:2000]}

### 수정된 파일 목록
{logs['files'][:800]}

### Git 커밋 로그
{logs['git'][:800]}

### 코드 변경 통계 (git diff)
{logs['diff'][:500]}

### 에러 로그
{logs['errors'][:400]}

### 기술 스택 감지 결과
{logs['tech_stack'][:300]}

### 커밋 메시지 품질 체크
{logs['commit_quality'][:300]}

### 반복 에러 패턴
{logs['error_patterns'][:300]}
"""

    if mode == "full":
        instruction = f"""# 전체 개발 히스토리 요약

## 📋 주요 작업 목록
(전체 히스토리에서 의미있는 작업들을 시간순으로 정리)

## 🛠 사용한 기술 스택
(감지된 기술 스택 기반으로 정리)

## 🐛 반복된 에러 패턴
(같은 에러를 여러 번 겪었다면 분석)

## 💡 학습 흔적

## ⚠️ 커밋 메시지 개선 제안
(품질 체크 결과 기반)

## 📊 전체 통계
- 총 명령어 수: (숫자)개
- 주로 사용한 기술: 
- 주로 사용한 명령어 TOP 5:
"""

    elif mode == "range":
        instruction = f"""# {label} 개발 기록

## 📋 기간 내 주요 작업
(날짜순으로 정리)

## 🛠 사용한 기술 스택

## 🐛 트러블슈팅 및 반복 에러

## 💡 배운 것들

## ⚠️ 커밋 메시지 개선 제안

## 📊 기간 통계
- 수정한 파일 수: (숫자)개
- Git 커밋 수: (숫자)개
- 추가된 코드: (숫자)줄
- 삭제된 코드: (숫자)줄
- 주로 사용한 기술:
"""

    elif mode == "project":
        instruction = f"""# {label} 프로젝트 기록

## 📌 프로젝트 개요
(파일 목록과 git 로그를 바탕으로 프로젝트 설명)

## 📋 작업 히스토리
(git 커밋 기록을 시간순으로 정리)

## 🛠 사용한 기술 스택

## 🐛 트러블슈팅

## ⚠️ 커밋 메시지 개선 제안

## 📊 프로젝트 통계
- 총 파일 수: (숫자)개
- Git 커밋 수: (숫자)개
- 추가된 코드: (숫자)줄
- 삭제된 코드: (숫자)줄
- 주요 언어:
- 작업 기간:
"""

    else:
        # daily
        instruction = f"""# {label} 개발 일지

## 📋 오늘 한 일
(오늘 진행한 작업을 3~5줄로 요약. 구체적으로.)

## 🛠 사용한 기술 스택
(감지된 기술 스택 기반으로 정리)

## 🐛 트러블슈팅
(발생한 문제와 해결 과정. 없으면 "없음"으로)

## ⚠️  반복 에러 경고
(같은 에러를 전에도 겪었다면 언급)

## ⚠️ 커밋 메시지 개선 제안
(품질 체크 결과 기반. 양호하면 "없음"으로)

## 💡 배운 것

## 📊 오늘의 통계
- 수정한 파일 수: (숫자)개
- Git 커밋 수: (숫자)개
- 추가된 코드: (숫자)줄
- 삭제된 코드: (숫자)줄
- 주로 사용한 기술:

## 🔜 내일 할 일
"""

    prompt = f"""당신은 개발자의 작업 로그를 분석해서 개발 일지를 작성하는 전문가입니다.

아래는 개발 활동 로그입니다.
---
{log_block}
---

위 로그를 바탕으로 아래 형식의 마크다운을 작성해주세요.
로그에 없는 내용은 추측하지 말고 "(데이터 없음)"으로 표시하세요.

{instruction}"""

    return prompt


def call_groq_api(prompt: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    body = {
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=30
    )
    if response.status_code != 200:
        raise Exception(f"API 오류: {response.status_code} - {response.text}")
    return response.json()["choices"][0]["message"]["content"]


def save_journal(filename: str, content: str) -> Path:
    filepath = JOURNAL_DIR / filename
    filepath.write_text(content, encoding="utf-8")
    print(f"✅ 저장 완료: {filepath}")
    return filepath


def main():
    args = sys.argv[1:]

    if not args:
        mode = "daily"
        today = datetime.now().strftime("%Y-%m-%d")
        log_subdir = LOG_DIR / today
        label = today
        filename = f"{today}.md"

    elif args[0] == "full":
        mode = "full"
        log_subdir = LOG_DIR / "full"
        label = "전체"
        filename = "full_summary.md"
        print("📚 전체 히스토리 요약 시작")

    elif args[0] == "range":
        if len(args) < 3:
            print("❌ 사용법: analyze.py range 2026-04-01 2026-04-12")
            sys.exit(1)
        mode = "range"
        date_from, date_to = args[1], args[2]
        log_subdir = LOG_DIR / f"range_{date_from}_{date_to}"
        label = f"{date_from} ~ {date_to}"
        filename = f"range_{date_from}_{date_to}.md"
        print(f"📅 날짜 범위 분석: {label}")

    elif args[0] == "project":
        if len(args) < 2:
            print("❌ 사용법: analyze.py project 프로젝트이름")
            sys.exit(1)
        mode = "project"
        project_name = args[1]
        log_subdir = LOG_DIR / f"project_{project_name}"
        label = project_name
        filename = f"project_{project_name}.md"
        print(f"🔍 프로젝트 분석: {project_name}")

    elif args[0] == "regenerate":
        # 재생성: 기존 로그 그대로, AI만 다시 호출
        target = args[1] if len(args) > 1 else datetime.now().strftime("%Y-%m-%d")
        print(f"🔄 재생성: {target}")
        if target.startswith("project_"):
            mode = "project"
            log_subdir = LOG_DIR / target
            label = target.replace("project_", "")
            filename = f"{target}.md"
        else:
            mode = "daily"
            log_subdir = LOG_DIR / target
            label = target
            filename = f"{target}.md"

    else:
        # 날짜 직접 지정
        mode = "daily"
        date_str = args[0]
        log_subdir = LOG_DIR / date_str
        label = date_str
        filename = f"{date_str}.md"
        print(f"🧠 AI 분석 시작: {date_str}")

    if not log_subdir.exists():
        print(f"⚠️  로그 폴더가 없습니다: {log_subdir}")
        print("   collect.sh를 먼저 실행하세요.")
        sys.exit(1)

    logs = load_logs(log_subdir)

    if all(v == "(없음)" for v in logs.values()):
        print("⚠️  수집된 로그가 없습니다.")
        sys.exit(1)

    prompt = build_prompt(mode, logs, label)

    print("📡 Groq API 호출 중...")
    journal_content = call_groq_api(prompt)

    save_journal(filename, journal_content)

    print("\n" + "="*50)
    print(journal_content[:500] + "...")
    print("="*50)


if __name__ == "__main__":
    main()

