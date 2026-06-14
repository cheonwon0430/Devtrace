# ai-summarizer

## 📌 프로젝트 소개
ai-summarizer 프로젝트는 Groq API 기반의 텍스트 요약기를 개발하는 프로젝트입니다. 이 프로젝트는 초기 구조를 설정하고, 이후 여러 번의 커밋을 통해 기능을 추가하고 개선했습니다.

## 🛠 기술 스택
사용한 기술 스택은 다음과 같습니다.
- Python: 4개 파일
- Shell: 1개 파일
- CSS: 2개 파일
- HTML: 1개 파일

## ✨ 주요 기능
주요 기능은 다음과 같습니다.
- 텍스트 요약 기능
- 파일 요약 기능
- `summarize_file` 함수를 추가하여 파일을 읽어서 요약 생성을 처리
- `FileNotFoundError`와 `ValueError`를 처리
- `chunk_text` 함수를 추가하여 긴 텍스트를 청킹하여 처리

## 🔥 개발 과정에서 해결한 문제들
개발 과정에서 해결한 문제들은 다음과 같습니다.
- `FileNotFoundError` 처리
- `ValueError` 처리
- `KeyError` 안전처리
- 401/KeyError 수정
- viewer.css 경로 수정

## 📈 개발 통계
- 개발 기간: 2026-06-13 ~ 2026-06-14 (2일)
- 총 커밋 수: 9개
- 총 수정 파일: 8개
- 추가된 코드: 315줄 / 삭제된 코드: 0줄

## 💡 배운 것들
배운 것들은 다음과 같습니다.
- 파일을 읽어서 요약 생성을 처리하는 방법
- `FileNotFoundError`와 `ValueError`를 처리하는 방법
- Python을 사용하여 ai-summarizer 프로젝트를 진행하는 방법