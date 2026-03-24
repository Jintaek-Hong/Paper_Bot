import feedparser
from google import genai
from notion_client import Client
from datetime import datetime, timedelta
import time
import os
import re
import sys

# Windows 환경 등에서 이모지 출력 시 발생하는 UnicodeEncodeError 방지
sys.stdout.reconfigure(encoding='utf-8')
# ==========================================
# 🚨 1. 여기에 발급받은 키와 ID를 다시 입력하세요!
# ==========================================
# GitHub Actions 설정 등을 위해 환경 변수 우선 적용
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ==========================================
# 🌐 2. 감시할 저널의 RSS 피드 주소 모음
# ==========================================
RSS_URLS = [
    "https://connect.biorxiv.org/biorxiv/category/cancer%20biology.xml",
    "https://www.nature.com/nature.rss",
    "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science",
    "https://www.nature.com/ni.rss",
    "https://www.nature.com/neuro.rss",
    "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciimmunol",
    "https://www.cell.com/action/showFeed?type=etoc&feed=rss&jc=immunity",
    "https://www.cell.com/action/showFeed?type=etoc&feed=rss&jc=neuron"
]

# ==========================================
# 🎯 3. 사용자 관심사 설정 (새로 추가됨)
# ==========================================
USER_INTERESTS = [
    "meningeal immunity", 
    "brain tumor",
    "CNS immunity",
    "autoimmune disease",
    "alzheimer's disease",
    "multiple sclerosis",
    "macrophage",
    "microglia",
    "astrocyte-microglia interaction",
    "neuroinflammation"
]

# ==========================================
# ⚙️ 4. AI 및 노션 세팅
# ==========================================
client = genai.Client(api_key=GEMINI_API_KEY)
notion = Client(auth=NOTION_TOKEN)

def run_paper_bot():
    print(f"총 {len(RSS_URLS)}개의 저널 사이트를 순찰합니다...\n")

    history_file = "evaluated_papers.txt"
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            evaluated_links = set(f.read().splitlines())
    else:
        evaluated_links = set()

    five_years_ago = datetime.now() - timedelta(days=365*5)
    global_relevant_entries = []

    # 1단계: 모든 피드를 돌며 1차 필터링된 논문들을 모두 모음
    for url in RSS_URLS:
        print(f"📡 접속 중: {url}")
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"⚠️ RSS 파싱 에러 발생 ({url}): {e}")
            continue

        candidates = []

        # 날짜와 중복 조건을 만족하는 논문 후보를 추립니다 (API 비용/시간 절약을 위해 최대 15개)
        for entry in feed.entries:
            if len(candidates) >= 15:
                break
                
            link = entry.link
            # 이미 평가한 논문인지 확인
            if link in evaluated_links:
                continue

            # 최근 5년 이내 논문인지 날짜 확인
            published_time = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_time = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_time = datetime(*entry.updated_parsed[:6])
            
            if published_time and published_time < five_years_ago:
                continue # 5년이 넘은 논문은 패스

            candidates.append(entry)

        # 후보가 있다면 AI에게 일괄로 의미적 연관성을 물어봅니다 (Semantic Filtering)
        if candidates:
            print(f"   🔍 검토할 새 논문 후보 {len(candidates)}개 발견. AI로 문맥 연관성 필터링 중...")
            
            prompt_lines = [
                f"내 연구 관심사: {', '.join(USER_INTERESTS)}",
                "아래는 최근 논문들의 제목과 초록입니다. 내 관심사와 '의미상' 관련된 논문들의 번호를 모두 찾아주세요.",
                "단순 키워 일치가 아니더라도 문맥상, 학술적으로 밀접한 관련이 있다면 포함하세요.",
                "답변은 반드시 연관된 논문의 번호만 쉼표로 구분해서 적어주세요. (예: 0, 2, 5) 연관된 논문이 하나도 없다면 '없음'이라고 적어주세요.\n",
                "후보 논문 목록:"
            ]
            
            for i, c in enumerate(candidates):
                c_title = c.title
                # 초록이 너무 길면 자릅니다
                c_abs = c.description[:600] + "..." if hasattr(c, 'description') and c.description else "초록 없음"
                prompt_lines.append(f"[{i}] 제목: {c_title}\n초록: {c_abs}\n")
                
            batch_prompt = "\n".join(prompt_lines)
            
            try:
                # 1차 필터링 호출 - 429 에러 방지를 위해 재시도 로직 추가
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        filter_response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=batch_prompt
                        )
                        time.sleep(15) # API Rate Limit(분당 5회) 완벽 보호를 위해 대기시간 15초로 대폭 증가
                        
                        resp_text = filter_response.text.strip()
                        if "없음" not in resp_text:
                            # 응답에서 숫자(인덱스)만 정규식으로 추출
                            indices = [int(num) for num in re.findall(r'\d+', resp_text)]
                            
                            # 중복 제거 및 유효한 인덱스만 걸러냄
                            for idx in sorted(list(set(indices))):
                                if 0 <= idx < len(candidates):
                                    global_relevant_entries.append(candidates[idx])
                        break # 성공시 반복문 탈출
                        
                    except Exception as api_err:
                        if "429" in str(api_err):
                            print(f"   [디버깅용 원본 에러 출력]: {api_err}")
                            print(f"   ⏳ API 분당 한도 초과(429). 65초 대기 후 재시도합니다... ({attempt+1}/{max_retries})")
                            time.sleep(65)
                        else:
                            print(f"   ⚠️ AI 필터링 중 에러 발생: {api_err}")
                            break # 429가 아닌 다른 에러면 포기
                                
            except Exception as e:
                print(f"   ⚠️ 알 수 없는 에러 발생: {e}")

    if not global_relevant_entries:
        print("\n⚠️ 전체 저널에서 새롭게 발견된 연관 논문이 없습니다. 봇을 종료합니다.")
        return

    # 2단계: 걸러진 논문들에 대해 상세 평가 및 점수 매기기 진행
    print(f"\n=====================================")
    print(f"🤖 총 {len(global_relevant_entries)}개의 연관 논문에 대해 심층 평가를 시작합니다...")
    
    scored_papers = []

    for entry in global_relevant_entries:
        title = entry.title
        link = entry.link
        abstract = entry.description if hasattr(entry, 'description') else "초록 없음"

        print(f"\n📄 평가 중: {title}")

        prompt = f"""
        너는 면역학, 분자생물학 연구자를 위한 '매우 엄격한' 전문 학술 비서이자 리뷰어 수준의 전문가야.
        내 목표는 매일 최고의 퀄리티를 가진 논문 3편만 엄선해서 뉴스레터로 읽는 것이야.
        아래 논문의 제목과 초록을 읽고, 내 관심사({', '.join(USER_INTERESTS)})와의 연관성 및 학술적 파급력을 매우 깐깐하게 평가해줘.
        특히 기존 연구와 차별화되는 참신함(Novelty)이나 학계에 미칠 영향(Impact)이 낮으면 가차없이 낮은 점수를 줘야해. (일반적인 논문은 4~6점, 정말 읽어볼 가치가 있는 뛰어난 논문만 7점 이상을 줘).

        논문 제목: {title}
        초록: {abstract}

        반드시 아래 양식에 맞춰서 답변해.
        [점수] (1부터 10까지 숫자만)
        [한줄요약] (이 논문을 꼭 읽어야 하는 이유를 포함하여 한국어로 1~2문장 요약)
        [상세분석] 1. 핵심 발견과 참신성 (Key Findings & Novelty)
        2. 연구의 파급력 (Significance & Impact)
        3. 실험 방법론의 특이점 (Methods)
        4. 한계점 (Limitations)
        이 4가지 카테고리를 활용해 뉴스레터처럼 읽기 쉽고 흥미롭게, 하지만 전문성을 잃지 않고 500자 이내로 요약해줘. 기존에 없던 관점이나 훌륭한 발견은 이모지나 시각적으로 돋보이게 강조해줘.
        """

        try:
            # 평가 완료 후 바로 평가 목록 파일에 저장합니다. (점수와 무관하게 더 이상 검토하지 않도록)
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(link + "\n")
            evaluated_links.add(link)

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    result_text = response.text

                    if "[점수]" in result_text and "[한줄요약]" in result_text:
                        score_str = result_text.split("[점수]")[1].split("[한줄요약]")[0].strip()
                        score = int(score_str)
                        short_summary = result_text.split("[한줄요약]")[1].split("[상세분석]")[0].strip()
                        detail_summary = result_text.split("[상세분석]")[1].strip()

                        print(f"⭐ AI 평가 점수: {score} / 10점")
                        
                        scored_papers.append({
                            "score": score,
                            "title": title,
                            "link": link,
                            "short_summary": short_summary,
                            "detail_summary": detail_summary
                        })
                    else:
                        print("⚠️ AI가 정해진 양식대로 답변하지 않았습니다.")
                    break # 성공시 반복문 탈출
                
                except Exception as api_err:
                    if "429" in str(api_err):
                        print(f"   [디버깅용 원본 에러 출력]: {api_err}")
                        print(f"   ⏳ API 분당 한도 초과(429). 65초 대기 후 재시도합니다... ({attempt+1}/{max_retries})")
                        time.sleep(65)
                    else:
                        print(f"   ⚠️ 에러 발생: {api_err}")
                        break

        except Exception as e:
            print(f"⚠️ 에러 발생: {e}")
        
        time.sleep(20) # 논문 심사 간 20초 간격으로 분당 3회 요청만 하도록 제한 

    # 3단계: 점수 순으로 정렬 후 최상위 3개 논문만 선별하여 노션 업로드
    if not scored_papers:
        print("\n⚠️ 최종적으로 정상 평가된 논문이 없습니다.")
        return

    scored_papers.sort(key=lambda x: x["score"], reverse=True)
    top_3_papers = scored_papers[:3]

    print(f"\n=====================================")
    print(f"🏆 전체 저널에서 가장 높은 점수를 받은 Top {len(top_3_papers)} 논문을 선별했습니다!")
    print("노션에 저장을 시작합니다...")

    today = datetime.now().strftime("%Y-%m-%d")

    for paper in top_3_papers:
        try:
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "논문 제목": {"title": [{"text": {"content": paper["title"]}}]},
                    "읽은 날짜": {"date": {"start": today}},
                    "핵심 요약": {"rich_text": [{"text": {"content": paper["short_summary"]}}]},
                    "URL": {"url": paper["link"]}
                },
                children=[
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": f"⭐ 점수: {paper['score']}/10\n\n🤖 AI 상세 분석:\n" + paper['detail_summary']}}]}
                    }
                ]
            )
            print(f"🎉 저장 완료: {paper['title']} ({paper['score']}점)")
        except Exception as e:
            print(f"⚠️ 노션 저장 에러: {e}")

if __name__ == "__main__":
    run_paper_bot()
