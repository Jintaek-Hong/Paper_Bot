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
# 모델명은 안정적인 서비스를 위해 gemini-1.5-flash를 기본으로 사용합니다.
MODEL_NAME = "gemini-1.5-flash"
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
    
    # 1단계: 모든 피드를 돌며 새 논문 후보들을 먼저 수집합니다.
    all_candidates = []
    print("📡 모든 RSS 피드에서 새로운 논문을 수집하고 있습니다...")
    
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"⚠️ RSS 파싱 에러 발생 ({url}): {e}")
            continue

        for entry in feed.entries:
            link = entry.link
            if link in evaluated_links:
                continue

            # 날짜 확인
            published_time = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_time = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_time = datetime(*entry.updated_parsed[:6])
            
            if published_time and published_time < five_years_ago:
                continue

            all_candidates.append(entry)
            # 너무 많은 후보가 쌓이는 것을 방지 (최대 100개)
            if len(all_candidates) >= 100:
                break
        
        if len(all_candidates) >= 100:
            break

    if not all_candidates:
        print("\n⚠️ 새롭게 발견된 논문이 없습니다. 봇을 종료합니다.")
        return

    print(f"🔍 총 {len(all_candidates)}개의 새 논문 후보를 발견했습니다. AI로 1차 필터링을 시작합니다.")

    # 2단계: 수집된 후보들을 30개씩 묶어서 일괄 필터링 (API 호출 횟수 절약)
    global_relevant_entries = []
    batch_size = 30
    
    for i in range(0, len(all_candidates), batch_size):
        batch = all_candidates[i:i+batch_size]
        print(f"   📦 배치 처리 중 ({i+1}~{min(i+batch_size, len(all_candidates))}/{len(all_candidates)})...")
        
        prompt_lines = [
            f"내 연구 관심사: {', '.join(USER_INTERESTS)}",
            "아래는 최근 논문들의 제목과 초록입니다. 내 관심사와 '의미상' 관련된 논문들의 번호를 모두 찾아주세요.",
            "답변은 반드시 연관된 논문의 번호만 쉼표로 구분해서 적어주세요. (예: 0, 2, 5) 연관된 논문이 하나도 없다면 '없음'이라고 적어주세요.\n",
            "후보 논문 목록:"
        ]
        
        for idx, c in enumerate(batch):
            c_title = c.title
            c_abs = c.description[:600] + "..." if hasattr(c, 'description') and c.description else "초록 없음"
            prompt_lines.append(f"[{idx}] 제목: {c_title}\n초록: {c_abs}\n")
            
        batch_prompt = "\n".join(prompt_lines)
        
        # 1차 필터링 호출
        max_retries = 3
        for attempt in range(max_retries):
            try:
                filter_response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=batch_prompt
                )
                time.sleep(20) # RPM 준수를 위한 대기 (1분당 3회 수준)
                
                resp_text = filter_response.text.strip()
                if "없음" not in resp_text:
                    indices = [int(num) for num in re.findall(r'\d+', resp_text)]
                    for idx in sorted(list(set(indices))):
                        if 0 <= idx < len(batch):
                            global_relevant_entries.append(batch[idx])
                break
            except Exception as api_err:
                if "429" in str(api_err):
                    print(f"   ⏳ API 한도 초과(429). 70초 대기 후 재시도합니다... ({attempt+1}/{max_retries})")
                    time.sleep(70)
                else:
                    print(f"   ⚠️ AI 필터링 중 에러 발생: {api_err}")
                    break

    if not global_relevant_entries:
        print("\n⚠️ 연구 관심사와 연관된 논문이 발견되지 않았습니다. 봇을 종료합니다.")
        return

    # 3단계: 걸러진 논문들에 대해 상세 평가 (최대 10개만 진행하여 API 고갈 방지)
    print(f"\n=====================================")
    print(f"🤖 총 {len(global_relevant_entries)}개의 연관 논문이 발견되었습니다.")
    eval_limit = 10
    if len(global_relevant_entries) > eval_limit:
        print(f"⚠️ API 한도 보호를 위해 상위 {eval_limit}개 논문만 상세 평가합니다.")
        global_relevant_entries = global_relevant_entries[:eval_limit]
    
    scored_papers = []

    for entry in global_relevant_entries:
        title = entry.title
        link = entry.link
        abstract = entry.description if hasattr(entry, 'description') else "초록 없음"

        print(f"\n📄 상세 평가 중: {title}")

        prompt = f"""
        너는 면역학, 분자생물학 전문가야. 아래 논문이 내 관심사({', '.join(USER_INTERESTS)})와 얼마나 밀접한지, 그리고 학술적 파급력이 어느 정도인지 평가해줘.
        7점 이상은 정말 중요한 논문, 4~6점은 일반적인 논문으로 평가해.

        논문 제목: {title}
        초록: {abstract}

        반드시 아래 양식에 맞춰서 답변해.
        [점수] (1부터 10까지 숫자만)
        [한줄요약] (한국어로 1~2문장 요약)
        [상세분석] (핵심 발견, 파급력, 방법론, 한계점을 포함하여 500자 이내 한국어 요약)
        """

        # 상세 평가 전에 미리 history에 추가 (실패하더라도 다시 평가하지 않도록)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(link + "\n")
        evaluated_links.add(link)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt
                )
                time.sleep(30) # 평가 간 30초 간격 유지 (RPM 안전 확보)
                
                result_text = response.text
                if "[점수]" in result_text and "[한줄요약]" in result_text:
                    score_str = result_text.split("[점수]")[1].split("[한줄요약]")[0].strip()
                    score = int(re.findall(r'\d+', score_str)[0])
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
                    print("⚠️ AI 응답 양식 불일치")
                break
            except Exception as api_err:
                if "429" in str(api_err):
                    print(f"   ⏳ API 한도 초과(429). 70초 대기 후 재시도합니다... ({attempt+1}/{max_retries})")
                    time.sleep(70)
                else:
                    print(f"   ⚠️ 에러 발생: {api_err}")
                    break

    # 4단계: 결과 정렬 및 노션 업로드
    if not scored_papers:
        print("\n⚠️ 최종적으로 정상 평가된 논문이 없습니다.")
        return

    scored_papers.sort(key=lambda x: x["score"], reverse=True)
    top_3_papers = scored_papers[:3]

    print(f"\n=====================================")
    print(f"🏆 Top {len(top_3_papers)} 논문 노션 저장을 시작합니다...")

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
