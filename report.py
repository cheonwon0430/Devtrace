#!/usr/bin/env python3
# ~/devtrace/report.py

import os
import sys
import requests
import re
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    nanum_fonts = [f for f in fm.findSystemFonts() if 'Nanum' in f or 'nanum' in f]
    preferred = [f for f in nanum_fonts if 'NanumGothic.ttf' in f or 'NanumSquareR.ttf' in f]
    font_path = preferred[0] if preferred else (nanum_fonts[0] if nanum_fonts else None)

    if font_path:
        fm.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = fm.FontProperties(fname=font_path).get_name()
    else:
        plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

load_dotenv(Path.home() / "devtrace" / "config.env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LOG_DIR = Path(os.getenv("LOG_DIR", str(Path.home() / "devtrace/logs")))
JOURNAL_DIR = Path(os.getenv("JOURNAL_DIR", str(Path.home() / "devtrace/journal")))
PORTFOLIO_DIR = Path(os.getenv("PORTFOLIO_DIR", str(Path.home() / "devtrace/portfolio")))

PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)


def get_api_config(provider: str) -> dict:
    if provider == "openai":
        return {
            "url": "https://api.openai.com/v1/chat/completions",
            "key": OPENAI_API_KEY,
            "model": "gpt-4o-mini",
        }
    else:
        return {
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "key": GROQ_API_KEY,
            "model": "llama-3.3-70b-versatile",
        }


def call_api(prompt: str, provider: str = "groq", max_tokens: int = 2000,
             temperature: float = 0.7, fallback_fn=None) -> str:
    config = get_api_config(provider)
    print(f"📡 {provider.upper()} API 호출 중...")

    def _do_request():
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['key']}"
        }
        body = {
            "model": config["model"],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 한국어로만 응답하는 개발 일지 작성 전문가입니다. 반드시 한국어로만 작성하세요."
                },
                {"role": "user", "content": prompt}
            ]
        }
        response = requests.post(
            config["url"],
            headers=headers,
            json=body,
            timeout=30
        )
        if response.status_code != 200:
            raise Exception(f"API 오류: {response.status_code} - {response.text}")
        return response.json()["choices"][0]["message"]["content"]

    try:
        return _do_request()
    except Exception as e:
        import time, re as _re
        msg = str(e)
        print(f"⚠️  API 호출 실패: {msg[:120]}")
        m = _re.search(r'try again in ([\d.]+)(s|m)', msg)
        if m:
            value, unit = float(m.group(1)), m.group(2)
            wait_sec = value if unit == 's' else value * 60
            if wait_sec <= 10:
                print(f"⏳ {wait_sec:.1f}초 후 재시도...")
                time.sleep(wait_sec)
                try:
                    return _do_request()
                except Exception as e2:
                    print(f"⚠️  재시도 실패: {str(e2)[:80]}")
            else:
                print(f"⏳ 대기 시간 {wait_sec:.0f}초 — 재시도 생략, 폴백으로 전환")
        if fallback_fn:
            print("📝 폴백으로 전환합니다.")
            return fallback_fn()
        raise


def load_week_journals(week_offset: int = 0) -> dict:
    today = datetime.now() - timedelta(weeks=week_offset)
    monday = today - timedelta(days=today.weekday())
    journals = {}
    for i in range(7):
        date = monday + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        filepath = JOURNAL_DIR / f"{date_str}.md"
        if filepath.exists():
            journals[date_str] = filepath.read_text(encoding="utf-8")
    return journals


def generate_weekly_report(journals: dict) -> str:
    if not journals:
        return "이번 주 기록된 일지가 없습니다."

    dates = sorted(journals.keys())
    week_start = dates[0]
    week_end = dates[-1]

    total_files = 0
    total_commits = 0
    prev_journals = load_week_journals(week_offset=1)

    for content in journals.values():
        m = re.search(r'수정한 파일 수.*?(\d+)', content)
        if m: total_files += int(m.group(1))
        m = re.search(r'Git 커밋 수.*?(\d+)', content)
        if m: total_commits += int(m.group(1))

    prev_commits = 0
    for content in prev_journals.values():
        m = re.search(r'Git 커밋 수.*?(\d+)', content)
        if m: prev_commits += int(m.group(1))

    if prev_commits > 0:
        growth = ((total_commits - prev_commits) / prev_commits) * 100
        growth_str = f"+{growth:.0f}% 📈" if growth > 0 else f"{growth:.0f}% 📉"
    else:
        growth_str = "첫 주 데이터"

    report = f"""# 📊 주간 리포트 ({week_start} ~ {week_end})

## 이번 주 통계
- 📅 활동한 날: {len(journals)}일
- 📁 수정한 파일: 총 {total_files}개
- 💾 Git 커밋: 총 {total_commits}개
- 📈 지난 주 대비 커밋: {growth_str}

## 일별 활동
"""
    for date, content in sorted(journals.items()):
        section = re.search(r'## 📋 오늘 한 일\n(.*?)\n##', content, re.DOTALL)
        summary = section.group(1).strip() if section else "기록 없음"
        first_line = summary.split('\n')[0]
        report += f"- **{date}**: {first_line}\n"

    return report


def generate_portfolio(project_name: str, template: str = "default",
                       provider: str = "groq") -> str:
    project_journals = []
    journal_dates = []

    template_content = ""
    if template != "default":
        template_path = Path.home() / "devtrace" / "templates" / f"{template}.md"
        if template_path.exists():
            template_content = template_path.read_text(encoding="utf-8")
            print(f"📄 템플릿 적용: {template}.md")
        else:
            print(f"⚠️  템플릿을 찾을 수 없습니다: {template}.md")

    for md_file in sorted(JOURNAL_DIR.glob(f"project_{project_name}*.md")):
        project_journals.append(md_file.read_text(encoding="utf-8"))

    keywords = [k for k in re.split(r'[-_]', project_name.lower()) if len(k) >= 3]
    if not keywords:
        keywords = [project_name.lower()]

    for md_file in sorted(JOURNAL_DIR.glob("20*.md")):
        content = md_file.read_text(encoding="utf-8")
        if any(k in content.lower() for k in keywords):
            project_journals.append(f"[{md_file.stem}]\n{content}")
            m = re.match(r'(\d{4}-\d{2}-\d{2})', md_file.stem)
            if m:
                journal_dates.append(m.group(1))

    if not project_journals:
        return f"'{project_name}' 관련 일지를 찾을 수 없습니다."

    total_files = 0
    total_commits = 0
    total_added = 0
    total_deleted = 0

    for content in project_journals:
        m = re.search(r'수정한 파일 수.*?(\d+)', content)
        if m: total_files += int(m.group(1))
        m = re.search(r'Git 커밋 수.*?(\d+)', content)
        if m: total_commits += int(m.group(1))
        m = re.search(r'추가된 코드.*?(\d+)', content)
        if m: total_added += int(m.group(1))
        m = re.search(r'삭제된 코드.*?(\d+)', content)
        if m: total_deleted += int(m.group(1))

    if journal_dates:
        journal_dates_sorted = sorted(set(journal_dates))
        if len(journal_dates_sorted) == 1:
            period_str = f"{journal_dates_sorted[0]} (1일)"
        else:
            period_str = f"{journal_dates_sorted[0]} ~ {journal_dates_sorted[-1]} ({len(journal_dates_sorted)}일)"
    else:
        period_str = "기록된 날짜 정보 없음"

    all_content = "\n\n---\n\n".join(project_journals)
    if len(all_content) > 8000:
        all_content = all_content[:8000] + "\n...(이하 생략)"

    if template_content:
        template_instruction = f"""
[템플릿 규칙]
아래 템플릿의 구조와 섹션을 반드시 유지하면서 내용을 채워줄 것.
템플릿에 없는 섹션은 추가하지 말 것.
템플릿의 섹션 순서를 바꾸지 말 것.

[템플릿]
{template_content}
"""
    else:
        template_instruction = f"""
# {project_name}

## 📌 프로젝트 소개

## 🛠 기술 스택

## ✨ 주요 기능

## 🔥 개발 과정에서 해결한 문제들

## 📈 개발 통계
- 개발 기간: {period_str}
- 총 커밋 수: {total_commits}개
- 총 수정 파일: {total_files}개
- 추가된 코드: {total_added}줄 / 삭제된 코드: {total_deleted}줄

## 💡 배운 것들
"""

    prompt = f"""당신은 개발자의 개발 일지를 읽고 GitHub 포트폴리오 README를 작성하는 전문가입니다.

아래는 "{project_name}" 프로젝트 관련 개발 일지 모음입니다.

{all_content}

[필수 규칙 - 언어]
1. 모든 문장은 순수 한국어로만 작성할 것 (Python/Git/API 등 기술 고유명사는 예외).
   금지 문자: 한자(漢字), 일본어 히라가나/가타카나(예: です, した), 베트남어 발음기호 알파벳.
   작성 후 전체를 다시 훑어보고 금지 문자 0개 상태로만 출력할 것.
   점검 과정이나 메타 설명은 출력에 포함하지 말 것.

[중요 - 개발 통계 작성 규칙]
아래 통계값을 절대 추측하거나 바꾸지 말고 그대로 사용할 것:
- 개발 기간: {period_str}
- 총 커밋 수: {total_commits}개
- 총 수정 파일: {total_files}개
- 추가된 코드: {total_added}줄 / 삭제된 코드: {total_deleted}줄

{template_instruction}
"""

    def portfolio_fallback():
        if template_content:
            fallback_text = f"# {project_name}\n\n"
            for line in template_content.split('\n'):
                if line.startswith('#'):
                    fallback_text += f"{line}\n"
                elif line.strip():
                    fallback_text += "(AI 호출 실패 — 직접 작성하세요)\n"
                else:
                    fallback_text += "\n"
            return fallback_text
        else:
            return f"""# {project_name}

## 📌 프로젝트 소개
(AI 호출 실패 — 직접 작성하세요)

## 🛠 기술 스택
(AI 호출 실패 — 직접 작성하세요)

## ✨ 주요 기능
(AI 호출 실패 — 직접 작성하세요)

## 📈 개발 통계
- 개발 기간: {period_str}
- 총 커밋 수: {total_commits}개
- 총 수정 파일: {total_files}개
- 추가된 코드: {total_added}줄 / 삭제된 코드: {total_deleted}줄
"""

    return call_api(prompt, provider=provider, temperature=0.3,
                    fallback_fn=portfolio_fallback)


def generate_interview_questions(project_name: str, provider: str = "groq") -> str:
    project_journals = []

    for md_file in sorted(JOURNAL_DIR.glob(f"project_{project_name}*.md")):
        project_journals.append(md_file.read_text(encoding="utf-8"))

    keywords = [k for k in re.split(r'[-_]', project_name.lower()) if len(k) >= 3]
    if not keywords:
        keywords = [project_name.lower()]

    for md_file in sorted(JOURNAL_DIR.glob("20*.md")):
        content = md_file.read_text(encoding="utf-8")
        if any(k in content.lower() for k in keywords):
            project_journals.append(f"[{md_file.stem}]\n{content}")

    if not project_journals:
        return f"'{project_name}' 관련 일지를 찾을 수 없습니다."

    all_content = "\n\n---\n\n".join(project_journals)
    if len(all_content) > 8000:
        all_content = all_content[:8000] + "\n...(이하 생략)"

    prompt = f"""당신은 신입 개발자의 기술 면접을 준비시키는 면접관입니다.

아래는 "{project_name}" 프로젝트의 개발 일지 모음입니다.

{all_content}

[필수 규칙]
1. 모든 문장은 순수 한국어로만 작성할 것 (Python/Git/API 등 기술 고유명사는 예외).
   금지 문자: 한자(漢字), 일본어 히라가나/가타카나(예: です, した, また),
   베트남어 발음기호 알파벳, 그 외 한국어가 아닌 모든 외국어.
   작성 후 전체를 다시 훑어보고 금지 문자 0개 상태로만 출력할 것.
2. 일지에 실제로 등장한 트러블슈팅/기술/커밋 내용을 바탕으로 질문을 만들 것.
3. 각 질문에 일지 내용 근거의 모범 답안을 1인칭으로 작성할 것.
4. 질문은 3개 카테고리로 총 5개:
   - 트러블슈팅 경험 (2개)
   - 기술 선택/구현 이유 (2개)
   - 협업/회고/배운 점 (1개)
5. placeholder 쓰지 말 것.

# {project_name} 면접 예상 질문

## 🔥 트러블슈팅 경험

### Q1.
**A1.**

### Q2.
**A2.**

## 🛠 기술 선택 / 구현

### Q3.
**A3.**

### Q4.
**A4.**

## 💡 협업 / 회고

### Q5.
**A5.**
"""

    return call_api(prompt, provider=provider, max_tokens=3000, temperature=0.3,
                    fallback_fn=lambda: f"# {project_name} 면접 예상 질문\n\n⚠️ AI 호출 실패 — 잠시 후 다시 실행하세요.")


def draw_weekly_graph(journals: dict):
    if not HAS_MATPLOTLIB:
        print("⚠️  matplotlib 없음 - 그래프 생략")
        return

    dates = []
    commits = []

    for date, content in sorted(journals.items()):
        dates.append(date[5:])
        m = re.search(r'Git 커밋 수.*?(\d+)', content)
        commits.append(int(m.group(1)) if m else 0)

    if not dates or all(c == 0 for c in commits):
        print("⚠️  커밋 데이터 없음 - 그래프 생략")
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(dates, commits, color='#4CAF50', alpha=0.8)
    ax.set_title('이번 주 일별 커밋 수', fontsize=14, pad=15)
    ax.set_xlabel('날짜')
    ax.set_ylabel('커밋 수')

    for bar, val in zip(bars, commits):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.05,
                   str(val), ha='center', va='bottom')

    plt.tight_layout()
    graph_path = PORTFOLIO_DIR / "weekly_graph.png"
    plt.savefig(graph_path, dpi=150)
    plt.close()
    print(f"📊 그래프 저장: {graph_path}")


def main():
    args = sys.argv[1:]

    # api provider 파싱 (마지막 인자가 groq/openai면 provider로 처리)
    api_provider = "groq"
    if args and args[-1] in ("groq", "openai"):
        api_provider = args[-1]
        args = args[:-1]

    mode = args[0] if args else "weekly"

    if mode == "weekly":
        print("📊 주간 리포트 생성 중...")
        journals = load_week_journals()
        report = generate_weekly_report(journals)
        week_num = datetime.now().strftime("%Y-W%U")
        filepath = JOURNAL_DIR / f"weekly_{week_num}.md"
        filepath.write_text(report, encoding="utf-8")
        print(f"✅ 주간 리포트 저장: {filepath}")
        draw_weekly_graph(journals)

    elif mode == "portfolio":
        project_name = args[1] if len(args) > 1 else "My Project"
        template = args[2] if len(args) > 2 else "default"
        print(f"🏗  포트폴리오 생성 중: {project_name} [API: {api_provider}]")
        readme = generate_portfolio(project_name, template, provider=api_provider)
        readme_path = PORTFOLIO_DIR / f"{project_name}_README.md"
        readme_path.write_text(readme, encoding="utf-8")
        print(f"✅ 포트폴리오 저장: {readme_path}")
        print("\n미리보기:")
        print(readme[:600])

    elif mode == "interview":
        project_name = args[1] if len(args) > 1 else "My Project"
        print(f"🎤 면접 질문 생성 중: {project_name} [API: {api_provider}]")
        result = generate_interview_questions(project_name, provider=api_provider)
        result_path = PORTFOLIO_DIR / f"{project_name}_interview.md"
        result_path.write_text(result, encoding="utf-8")
        print(f"✅ 면접 질문 저장: {result_path}")
        print("\n미리보기:")
        print(result[:600])


    elif mode == "coverletter":
        project_name = args[1] if len(args) > 1 else "My Project"
        questions = args[2] if len(args) > 2 else ""
        print(f"📝 자기소개서 생성 중: {project_name} [API: {api_provider}]")
        result = generate_coverletter(project_name, questions, provider=api_provider)
        result_path = PORTFOLIO_DIR / f"{project_name}_coverletter.md"
        result_path.write_text(result, encoding="utf-8")
        print(f"✅ 자기소개서 저장: {result_path}")
        print("\n미리보기:")
        print(result[:600])

    else:
        print("사용법:")
        print("  report.py weekly              → 주간 리포트")
        print("  report.py portfolio [이름]    → 포트폴리오 생성")
        print("  report.py interview [이름]    → 면접 질문 생성")


if __name__ == "__main__":
    main()


def generate_coverletter(project_name: str, questions: str, provider: str = "groq") -> str:
    """자기소개서 항목 기반 답변 생성"""
    project_journals = []

    for md_file in sorted(JOURNAL_DIR.glob(f"project_{project_name}*.md")):
        project_journals.append(md_file.read_text(encoding="utf-8"))

    keywords = [k for k in re.split(r'[-_]', project_name.lower()) if len(k) >= 3]
    if not keywords:
        keywords = [project_name.lower()]

    for md_file in sorted(JOURNAL_DIR.glob("20*.md")):
        content = md_file.read_text(encoding="utf-8")
        if any(k in content.lower() for k in keywords):
            project_journals.append(f"[{md_file.stem}]\n{content}")

    if not project_journals:
        return f"'{project_name}' 관련 일지를 찾을 수 없습니다."

    all_content = "\n\n---\n\n".join(project_journals)
    if len(all_content) > 8000:
        all_content = all_content[:8000] + "\n...(이하 생략)"

    prompt = f"""당신은 신입 개발자의 자기소개서를 작성해주는 전문가입니다.

아래는 "{project_name}" 프로젝트의 개발 일지 모음입니다.
이 일지를 바탕으로 아래 자기소개서 항목에 답변을 작성해주세요.

[개발 일지]
{all_content}

[자기소개서 항목]
{questions}

[자기소개서 작성 전 필수 분석]
각 항목을 작성하기 전에 아래 평가 의도를 반드시 먼저 파악하고 그에 맞게 작성할 것.

1번 항목 평가 의도: 표면적 에러 수정이 아닌 구조적 취약점 발견 능력.
핵심: "에러가 발생했다 → 고쳤다"가 아니라 "왜 이 구조가 그 에러를 만들어냈는가"를 발견한 서사로 작성할 것.
예시 흐름: API 키를 코드에 직접 넣었다 → 보안 취약점 발생 → 왜 이 설계가 문제인지 인식 → .env 구조로 전환
절대 금지: "파일 경로를 확인했습니다", "키가 존재하는지 확인했습니다" 같은 단순 수정 나열.

2번 항목 평가 의도: 완성도에 대한 집착과 몰입 경험.
핵심: "충분하다고 느꼈던 시점"을 구체적으로 언급하고, "그럼에도 더 한 이유"와 "그 과정의 구체적 어려움"을 써야 함.
절대 금지: 통계 수치 나열, 에러 해결 나열, "몰입했습니다" 선언만 하고 근거 없음.

3번 항목 평가 의도: 각 기술 분야에 대한 실제 경험 기반 관심도.
핵심: 순위 형식(Platform > Client = Server > Infra) 먼저 쓰고, 각 분야마다 ai-summarizer에서 실제로 한 작업을 근거로 관심 갖게 된 계기를 구체적으로 작성할 것.
절대 금지: "~할 예정입니다", "~의 중요성을 깨달았습니다"만 쓰고 구체적 경험 없음, Infra를 Git으로 퉁치기.

공통 금지사항:
- 통계 수치(파일 수, 커밋 수, 코드 줄 수) 절대 포함 금지
- "~했습니다. ~했습니다" 단순 나열 금지
- 상황 → 문제 인식 → 시도 → 해결 → 깨달음 구조로 작성할 것
- 1인칭 서사, 감정과 성장이 느껴지도록 작성할 것

[필수 규칙]
1. 모든 문장은 순수 한국어로만 작성할 것 (Python/Git/API 등 기술 고유명사는 예외).
   금지 문자: 한자(漢字), 일본어 히라가나/가타카나, 베트남어 발음기호 알파벳.
   작성 후 전체를 다시 훑어보고 금지 문자 0개 상태로만 출력할 것.
2. 반드시 일지에 실제로 등장한 경험/트러블슈팅/기술을 근거로 작성할 것.
   일지에 없는 내용은 억지로 만들지 말 것.
3. 각 항목별 글자 수 제한이 있으면 그 안에서 작성할 것.
4. 1인칭(저는, 제가)으로 작성할 것.
5. 각 항목은 원래 질문 번호와 내용을 헤더로 유지할 것.
6. placeholder 쓰지 말 것.

위 항목들에 대해 개발 일지 내용을 근거로 자기소개서 답변을 작성해주세요.
"""

    return call_api(
        prompt, provider=provider, max_tokens=3500, temperature=0.4,
        fallback_fn=lambda: f"# {project_name} 자기소개서\n\n⚠️ AI 호출 실패 — 잠시 후 다시 실행하세요."
    )

