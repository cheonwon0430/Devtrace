#!/usr/bin/env python3
# ~/devtrace/analyze.py

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


def count_files(files_txt: str) -> int:
    if files_txt == "(없음)":
        return 0
    return len([l for l in files_txt.strip().split("\n") if l.strip()])


def has_meaningful_history(history: str) -> bool:
    if history == "(없음)":
        return False
    lines = [l.strip() for l in history.strip().split("\n") if l.strip()]
    return len(lines) >= 3


def clean_tech_stack(tech: str) -> str:
    """기술 스택 텍스트 정리 - 헤더 제거 + 들여쓰기 제거"""
    if tech == "(없음)":
        return "(없음)"
    lines = tech.replace("## 기술 스택 감지", "").strip().split("\n")
    cleaned = "\n".join(l.strip() for l in lines if l.strip())
    return cleaned if cleaned else "(없음)"


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


def generate_empty_template(mode: str, label: str, logs: dict) -> str:
    """히스토리 없을 때 기본 템플릿 반환 (AI 호출 없음)"""
    total_files = count_files(logs["files"])
    git = logs["git"]
    tech = clean_tech_stack(logs["tech_stack"])
    commit_count = git.count("[") if git != "(없음)" else 0

    if mode == "project":
        return f"""# {label} 프로젝트 기록

## 📌 프로젝트 개요
(터미널 활동 기록이 없어 상세 분석 불가)

## 📋 작업 히스토리
{git if git != "(없음)" else "커밋 기록 없음"}

## 🛠 사용한 기술 스택
{tech}

## 🐛 트러블슈팅
(터미널 활동 기록 없음 - 분석 불가)

## ⚠️ 커밋 메시지 개선 제안
{logs['commit_quality'] if logs['commit_quality'] != "(없음)" else "없음"}

## 📊 프로젝트 통계
- 총 파일 수: {total_files}개
- Git 커밋 수: {commit_count}개
- 추가된 코드: 변경 사항이 기록되지 않았습니다
- 삭제된 코드: 변경 사항이 기록되지 않았습니다
- 주요 언어: 기술 스택 항목을 참고해주세요
- 작업 기간: 작업 기간을 확인할 수 없습니다
"""

    elif mode in ("range", "full"):
        return f"""# {label} 개발 기록

## 📋 주요 작업
(터미널 활동 기록이 없어 상세 분석 불가)

## 🛠 사용한 기술 스택
{tech}

## 🐛 트러블슈팅
(터미널 활동 기록 없음 - 분석 불가)

## 📊 통계
- 수정한 파일 수: {total_files}개
- Git 커밋 수: {commit_count}개
"""

    else:
        # daily
        return f"""# {label} 개발 일지

## 📋 오늘 한 일
오늘 터미널 활동 기록이 없습니다.
파일 변경은 {total_files}개 감지됐으나 작업 내용을 확인할 수 없습니다.
내일부터는 터미널 히스토리가 자동으로 기록됩니다.

## 🛠 사용한 기술 스택
{tech}

## 🐛 트러블슈팅
없음

## ⚠️ 반복 에러 경고
없음

## ⚠️ 커밋 메시지 개선 제안
없음

## 💡 배운 것
오늘은 터미널 활동 기록이 없어 배운 점을 분석할 수 없습니다.

## 📊 오늘의 통계
- 수정한 파일 수: {total_files}개
- Git 커밋 수: {commit_count}개
- 추가된 코드: 변경 사항이 기록되지 않았습니다
- 삭제된 코드: 변경 사항이 기록되지 않았습니다
- 주로 사용한 기술: 기술 스택 항목을 참고해주세요

## 🔜 내일 할 일
아직 계획이 기록되지 않았습니다.
"""


def build_prompt(mode: str, logs: dict, label: str = "") -> str:

    total_files = count_files(logs["files"])
    tech = clean_tech_stack(logs["tech_stack"])

    log_block = f"""
### 터미널 히스토리
{logs['history'][:2000]}

### 수정된 파일 목록 (총 {total_files}개)
{logs['files'][:800]}

### Git 커밋 로그
{logs['git'][:800]}

### 코드 변경 통계 (git diff)
{logs['diff'][:500]}

### 에러 로그 (개발 에러만)
{logs['errors'][:400]}

### 기술 스택 감지 결과
{tech}

### 커밋 메시지 품질 체크
{logs['commit_quality'][:300]}

### 반복 에러 패턴
{logs['error_patterns'][:300]}
"""

    common_rules = f"""
[필수 규칙 - 반드시 지켜야 함]
1. 모든 출력은 반드시 한국어로만 작성할 것. 영어 단어, 일본어(예: また, です), 중국어
   글자가 단 한 글자라도 섞이면 안 됨. 작성 후 스스로 다시 읽고 한국어가 아닌
   문자가 있으면 그 부분을 한국어로 고쳐서 출력할 것.
2. 기술 용어(Python, Git, React 등 영문 고유명사)는 그대로 써도 되지만 문장 자체는 반드시 한국어로.
3. 로그에 정보가 없을 때는 "(데이터 없음)" 같은 placeholder 문자열을 절대 쓰지 말 것.
   대신 짧은 한국어 문장으로 자연스럽게 표현할 것.
   예: "오늘은 기록된 트러블슈팅이 없습니다.", "내일 할 일은 아직 정해지지 않았습니다."
4. 시스템 에러(gnome, dbus, pulseaudio, sudo 권한 등)는 트러블슈팅에 포함하지 말 것.
5. 개발 관련 에러만 트러블슈팅에 포함할 것.
6. 총 파일 수는 반드시 {total_files}개로 표시할 것.
7. 아래 [형식]에 주어진 섹션 헤더(이모지 포함)를 글자 그대로, 빠짐없이 사용할 것.
   이모지를 빼거나 다른 이모지로 바꾸지 말 것.
"""

    if mode == "full":
        instruction = f"""# 전체 개발 히스토리 요약

## 📋 주요 작업 목록
(전체 히스토리에서 의미있는 작업들을 시간순으로 정리)

## 🛠 사용한 기술 스택
{tech}

## 🐛 반복된 에러 패턴
(같은 에러를 여러 번 겪었다면 분석, 없으면 "없음")

## 💡 학습 흔적

## ⚠️ 커밋 메시지 개선 제안
(품질 체크 결과 기반, 양호하면 "없음")

## 📊 전체 통계
- 총 파일 수: {total_files}개
- 주로 사용한 기술:
- 주로 사용한 명령어 TOP 5:
"""

    elif mode == "range":
        instruction = f"""# {label} 개발 기록

## 📋 기간 내 주요 작업
(날짜순으로 정리)

## 🛠 사용한 기술 스택

## 🐛 트러블슈팅
(개발 관련 에러만, 없으면 "없음")

## 💡 배운 것들

## ⚠️ 커밋 메시지 개선 제안
(양호하면 "없음")

## 📊 기간 통계
- 수정한 파일 수: {total_files}개
- Git 커밋 수: (git 로그에서 계산)개
- 추가된 코드: (diff에서 확인)줄
- 삭제된 코드: (diff에서 확인)줄
- 주로 사용한 기술:
"""

    elif mode == "project":
        instruction = f"""# {label} 프로젝트 기록

## 📌 프로젝트 개요
(파일 목록과 git 로그를 바탕으로 프로젝트 설명)

## 📋 작업 히스토리
(git 커밋 기록을 날짜별로 정리)

## 🛠 사용한 기술 스택
{tech}

## 🐛 트러블슈팅
(개발 관련 에러만, 없으면 "없음")

## ⚠️ 커밋 메시지 개선 제안
(양호하면 "없음")

## 📊 프로젝트 통계
- 총 파일 수: {total_files}개
- Git 커밋 수: (git 로그에서 계산)개
- 추가된 코드: (diff에서 확인)줄
- 삭제된 코드: (diff에서 확인)줄
- 주요 언어: (tech_stack에서 가장 많은 것)
- 작업 기간: (첫 커밋 ~ 마지막 커밋)
"""

    else:
        instruction = f"""# {label} 개발 일지

## 📋 오늘 한 일
(오늘 진행한 작업을 3~5줄로 요약. 구체적으로. 절대 추측하지 말 것.)

## 🛠 사용한 기술 스택
{tech}

## 🐛 트러블슈팅
(개발 관련 에러만. 시스템 에러 제외. 없으면 "없음")

## ⚠️ 반복 에러 경고
(같은 에러를 전에도 겪었다면 언급, 없으면 "없음")

## ⚠️ 커밋 메시지 개선 제안
(품질 체크 결과 기반. 양호하면 "없음")

## 💡 배운 것

## 📊 오늘의 통계
- 수정한 파일 수: {total_files}개
- Git 커밋 수: (git 로그에서 계산)개
- 추가된 코드: (diff에서 확인)줄
- 삭제된 코드: (diff에서 확인)줄
- 주로 사용한 기술:

## 🔜 내일 할 일
"""

    prompt = f"""당신은 개발자의 작업 로그를 분석해서 개발 일지를 작성하는 전문가입니다.

{common_rules}

아래는 개발 활동 로그입니다.
---
{log_block}
---

위 로그를 바탕으로 아래 형식의 마크다운을 작성해주세요.

{instruction}"""

    return prompt


def call_groq_api(prompt: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    body = {
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 3500,
        "messages": [
            {
                "role": "system",
                "content": "당신은 한국어로만 응답하는 개발 일지 작성 전문가입니다. 반드시 한국어로만 작성하세요. 영어 문장, 일본어, 중국어는 절대 사용하지 마세요."
            },
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=body,
        timeout=30
    )
    if response.status_code != 200:
        raise Exception(f"API 오류: {response.status_code} - {response.text}")

    data = response.json()
    choice = data["choices"][0]
    if choice.get("finish_reason") == "length":
        print("⚠️  응답이 토큰 한도로 잘렸을 수 있습니다 (finish_reason=length)")
    return choice["message"]["content"]


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

    # 히스토리가 없으면 AI 호출 없이 기본 템플릿 출력
    if not has_meaningful_history(logs["history"]):
        print("ℹ️  터미널 히스토리가 없어 기본 템플릿으로 저장합니다.")
        journal_content = generate_empty_template(mode, label, logs)
    else:
        prompt = build_prompt(mode, logs, label)
        print("📡 Groq API 호출 중...")
        journal_content = call_groq_api(prompt)

    save_journal(filename, journal_content)

    print("\n" + "="*50)
    print(journal_content[:500] + "...")
    print("="*50)


if __name__ == "__main__":
    main()

