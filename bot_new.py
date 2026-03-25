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
MODEL_NAME = "gemini-2.5-flash"
client = genai.Client(api_key=GEMINI_API_KEY)
notion = Client(auth=NOTION_TOKEN)

# ==========================================
# 🔑 5. 로컬 키워드 사전 필터링 (API 호출 제로)
# ==========================================
def keyword_prefilter(title, abstract):
    """제목과 초록에서 관심 키워드가 하나라도 있으면 True 반환"""
    text = (title + " " + abstract).lower()
    for interest in USER_INTERESTS:
        if interest.lower() in text:
            return True
    return False

def run_paper_bot():
    print(f"총 {len(RSS_URLS)}개의 저널 사이트를 순찰합니다...\n")

    history_file = "evaluated_papers.txt"
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            evaluated_links = set(f.read().splitlines())
    else:
        evaluated_links = set()

    five_years_ago = datetime.now() - timedelta(days=365*5)
    
    # ===== 1단계: RSS 수집 + 로컬 키워드 사전 필터링 (API 호출 0회) =====
    keyword_matched = []
    total_new = 0
    print("📡 모든 RSS 피드에서 논문을 수집하고 키워드 사전 필터링 중...")
    
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"⚠️ RSS 파싱 에러 ({url}): {e}")
            continue

        for entry in feed.entries:
            link = entry.link
            if link in evaluated_links:
                continue

            published_time = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_time = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_time = datetime(*entry.updated_parsed[:6])
            
            if published_time and published_time < five_years_ago:
                continue

            total_new += 1
            title = entry.title
            abstract = entry.description if hasattr(entry, 'description') and entry.description else ""
            
            if keyword_prefilter(title, abstract):
                keyword_matched.append(entry)

    print(f"   📊 새 논문 {total_new}개 중 키워드 매칭된 후보: {len(keyword_matched)}개")

    if not keyword_matched:
        print("\n⚠️ 키워드와 일치하는 새 논문이 없습니다. 봇을 종료합니다.")
        return

    # 키워드 매칭 후보가 너무 많으면 상위 20개로 제한
    if len(keyword_matched) > 20:
        print(f"   ✂️ 후보가 많아 상위 20개로 제한합니다.")
        keyword_matched = keyword_matched[:20]

    # ===== 2단계: AI 의미 필터링 (API 호출 1회) =====
    print(f"\n🤖 [AI 호출 1/2] {len(keyword_matched)}개 후보에 대해 의미적 연관성 필터링 중...")
    
    prompt_lines = [
        f"내 연구 관심사: {', '.join(USER_INTERESTS)}",
        "아래는 최근 논문들의 제목과 초록입니다. 내 관심사와 '의미상' 깊이 관련된 논문들의 번호를 찾아주세요.",
        "단순 키워드 일치가 아닌, 학술적으로 밀접한 관련이 있는 논문만 선별하세요.",
        "답변은 연관된 논문의 번호만 쉼표로 구분해서 적어주세요. (예: 0, 2, 5) 없으면 '없음'\n",
        "후보 논문 목록:"
    ]
    
    for idx, c in enumerate(keyword_matched):
        c_title = c.title
        c_abs = c.description[:500] + "..." if hasattr(c, 'description') and c.description else "초록 없음"
        prompt_lines.append(f"[{idx}] 제목: {c_title}\n초록: {c_abs}\n")
        
    batch_prompt = "\n".join(prompt_lines)
    
    relevant_entries = []
    max_retries = 3
    for attempt in range(max_retries):
        try:
            filter_response = client.models.generate_content(
                model=MODEL_NAME,
                contents=batch_prompt
            )
            resp_text = filter_response.text.strip()
            if "없음" not in resp_text:
                indices = [int(num) for num in re.findall(r'\d+', resp_text)]
                for idx in sorted(list(set(indices))):
                    if 0 <= idx < len(keyword_matched):
                        relevant_entries.append(keyword_matched[idx])
            print(f"   ✅ AI 필터링 완료: {len(relevant_entries)}개 연관 논문 발견")
            break
        except Exception as api_err:
            if "429" in str(api_err):
                print(f"   ⏳ API 한도 초과(429). 70초 대기 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(70)
            else:
                print(f"   ⚠️ AI 필터링 에러: {api_err}")
                break

    if not relevant_entries:
        print("\n⚠️ AI 필터링 결과 연관 논문이 없습니다. 봇을 종료합니다.")
        # 키워드 매칭된 논문들도 평가 완료로 기록
        with open(history_file, "a", encoding="utf-8") as f:
            for entry in keyword_matched:
                f.write(entry.link + "\n")
        return

    # 상세 평가 대상은 최대 5개로 제한
    if len(relevant_entries) > 5:
        relevant_entries = relevant_entries[:5]

    # ===== 3단계: AI 일괄 상세 평가 (API 호출 1회) =====
    print(f"\n🤖 [AI 호출 2/2] {len(relevant_entries)}개 논문 일괄 상세 평가 중...")
    
    eval_prompt_lines = [
        f"너는 면역학, 분자생물학 전문가야. 내 관심사: {', '.join(USER_INTERESTS)}",
        "아래 논문들을 각각 평가해줘. 7점 이상은 정말 중요한 논문, 4~6점은 일반적인 논문.",
        "반드시 각 논문마다 아래 양식을 사용해서 답변해:\n",
        "===논문[번호]===",
        "[점수] (1~10 숫자만)",
        "[한줄요약] (한국어 1~2문장)",
        "[상세분석] (핵심 발견, 파급력, 방법론, 한계점 포함 500자 이내 한국어)\n",
        "평가할 논문 목록:"
    ]
    
    for idx, entry in enumerate(relevant_entries):
        title = entry.title
        abstract = entry.description[:500] if hasattr(entry, 'description') and entry.description else "초록 없음"
        eval_prompt_lines.append(f"\n===논문[{idx}]===\n제목: {title}\n초록: {abstract}")
    
    eval_prompt = "\n".join(eval_prompt_lines)
    
    scored_papers = []
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=eval_prompt
            )
            result_text = response.text
            
            # 각 논문별 결과 파싱
            for idx, entry in enumerate(relevant_entries):
                try:
                    # 해당 논문의 평가 섹션 추출
                    marker = f"===논문[{idx}]==="
                    next_marker = f"===논문[{idx+1}]==="
                    
                    if marker in result_text:
                        if next_marker in result_text:
                            section = result_text.split(marker)[1].split(next_marker)[0]
                        else:
                            section = result_text.split(marker)[1]
                        
                        if "[점수]" in section and "[한줄요약]" in section:
                            score_str = section.split("[점수]")[1].split("[한줄요약]")[0].strip()
                            score = int(re.findall(r'\d+', score_str)[0])
                            
                            short_summary = section.split("[한줄요약]")[1]
                            if "[상세분석]" in short_summary:
                                detail_summary = short_summary.split("[상세분석]")[1].strip()
                                short_summary = short_summary.split("[상세분석]")[0].strip()
                            else:
                                detail_summary = "상세 분석 없음"
                                short_summary = short_summary.strip()
                            
                            print(f"   ⭐ [{idx}] {entry.title[:50]}... → {score}점")
                            scored_papers.append({
                                "score": score,
                                "title": entry.title,
                                "link": entry.link,
                                "short_summary": short_summary,
                                "detail_summary": detail_summary
                            })
                except Exception as parse_err:
                    print(f"   ⚠️ 논문[{idx}] 파싱 실패: {parse_err}")
            
            print(f"   ✅ 일괄 평가 완료: {len(scored_papers)}개 정상 평가됨")
            break
        except Exception as api_err:
            if "429" in str(api_err):
                print(f"   ⏳ API 한도 초과(429). 70초 대기 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(70)
            else:
                print(f"   ⚠️ 평가 에러: {api_err}")
                break

    # 평가한 논문들을 히스토리에 기록
    with open(history_file, "a", encoding="utf-8") as f:
        for entry in relevant_entries:
            f.write(entry.link + "\n")

    # ===== 4단계: 노션 업로드 =====
    if not scored_papers:
        print("\n⚠️ 최종 평가된 논문이 없습니다.")
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
