import feedparser
from google import genai
from notion_client import Client
from datetime import datetime, timedelta
import time
import os

# ==========================================
# ?š¨ 1. ?¬ê¸°??ë°œê¸‰ë°›ì? ?¤ì? IDë¥??¤ì‹œ ?…ë ¥?˜ì„¸??
# ==========================================
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ==========================================
# ?Œ 2. ê°ì‹œ???€?ì˜ RSS ?¼ë“œ ì£¼ì†Œ ëª¨ìŒ
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
# ?¯ 3. ?¬ìš©??ê´€?¬ì‚¬ ?¤ì • (?ˆë¡œ ì¶”ê???
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
# ?™ï¸ 4. AI ë°??¸ì…˜ ?¸íŒ…
# ==========================================
client = genai.Client(api_key=GEMINI_API_KEY)
notion = Client(auth=NOTION_TOKEN)

def run_paper_bot():
    print(f"ì´?{len(RSS_URLS)}ê°œì˜ ?€???¬ì´?¸ë? ?œì°°?©ë‹ˆ??..\n")

    # ?“ [?ˆë¡œ ì¶”ê?] ?´ë? ?‰ê????¼ë¬¸ ê¸°ë¡ ë¶ˆëŸ¬?¤ê¸° (ì¤‘ë³µ ë°©ì???
    history_file = "evaluated_papers.txt"
    if os.path.e    # ??[?˜ì •?? 5????? ì§œ ê³„ì‚°
    five_years_ago = datetime.now() - timedelta(days=365*5)

    global_relevant_entries = []

    # 1?¨ê³„: ëª¨ë“  ?¼ë“œë¥??Œë©° 1ì°??„í„°ë§ëœ ?¼ë¬¸?¤ì„ ëª¨ë‘ ëª¨ìŒ
    for url in RSS_URLS:
        print(f"?“¡ ?‘ì† ì¤? {url}")
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"? ï¸ RSS ?Œì‹± ?ëŸ¬ ë°œìƒ ({url}): {e}")
            continue

        candidates = []

        # ? ì§œ?€ ì¤‘ë³µ ì¡°ê±´??ë§Œì¡±?˜ëŠ” ?¼ë¬¸ ?„ë³´ë¥?ì¶”ë¦½?ˆë‹¤ (API ë¹„ìš©/?œê°„ ?ˆì•½???„í•´ ìµœë? 15ê°?
        for entry in feed.entries:
            if len(candidates) >= 15:
                break
                
            link = entry.link
            # ?´ë? ?‰ê????¼ë¬¸?¸ì? ?•ì¸
            if link in evaluated_links:
                continue

            # ìµœê·¼ 5???´ë‚´ ?¼ë¬¸?¸ì? ? ì§œ ?•ì¸
            published_time = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_time = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_time = datetime(*entry.updated_parsed[:6])
            
            if published_time and published_time < five_years_ago:
                continue # 5?„ì´ ?˜ì? ?¼ë¬¸?€ ?¨ìŠ¤

            candidates.append(entry)

        # ?„ë³´ê°€ ?ˆë‹¤ë©?AI?ê²Œ ?¼ê´„ë¡??˜ë????°ê??±ì„ ë¬¼ì–´ë´…ë‹ˆ??(Semantic Filtering)
        if candidates:
            print(f"   ?” ê²€? í•  ???¼ë¬¸ ?„ë³´ {len(candidates)}ê°?ë°œê²¬. AIë¡?ë¬¸ë§¥ ?°ê????„í„°ë§?ì¤?..")
            
            prompt_lines = [
                f"???°êµ¬ ê´€?¬ì‚¬: {', '.join(USER_INTERESTS)}",
                "?„ë˜??ìµœê·¼ ?¼ë¬¸?¤ì˜ ?œëª©ê³?ì´ˆë¡?…ë‹ˆ?? ??ê´€?¬ì‚¬?€ '?˜ë??? ê´€?¨ëœ ?¼ë¬¸?¤ì˜ ë²ˆí˜¸ë¥?ëª¨ë‘ ì°¾ì•„ì£¼ì„¸??",
                "?¨ìˆœ ?¤ì›Œ???¼ì¹˜ê°€ ?„ë‹ˆ?”ë¼??ë¬¸ë§¥?? ?™ìˆ ?ìœ¼ë¡?ë°€?‘í•œ ê´€?¨ì´ ?ˆë‹¤ë©??¬í•¨?˜ì„¸??",
                "?µë??€ ë°˜ë“œ???°ê????¼ë¬¸??ë²ˆí˜¸ë§??¼í‘œë¡?êµ¬ë¶„?´ì„œ ?ì–´ì£¼ì„¸?? (?? 0, 2, 5) ?°ê????¼ë¬¸???˜ë‚˜???†ë‹¤ë©?'?†ìŒ'?´ë¼ê³??ì–´ì£¼ì„¸??\n",
                "?„ë³´ ?¼ë¬¸ ëª©ë¡:"
            ]
            
            for i, c in enumerate(candidates):
                c_title = c.title
                # ì´ˆë¡???ˆë¬´ ê¸¸ë©´ ?ë¦…?ˆë‹¤
                c_abs = c.description[:600] + "..." if hasattr(c, 'description') and c.description else "ì´ˆë¡ ?†ìŒ"
                prompt_lines.append(f"[{i}] ?œëª©: {c_title}\nì´ˆë¡: {c_abs}\n")
                
            batch_prompt = "\n".join(prompt_lines)
            
            try:
                import re
                # 1ì°??„í„°ë§??¸ì¶œ
                filter_response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=batch_prompt
                )
                time.sleep(3) # API Rate Limit ë³´í˜¸ë¥??„í•œ ì§§ì? ?€ê¸?                
                resp_text = filter_response.text.strip()
                if "?†ìŒ" not in resp_text:
                    # ?‘ë‹µ?ì„œ ?«ì(?¸ë±??ë§??•ê·œ?ìœ¼ë¡?ì¶”ì¶œ
                    indices = [int(num) for num in re.findall(r'\d+', resp_text)]
                    
                    # ì¤‘ë³µ ?œê±° ë°?? íš¨???¸ë±?¤ë§Œ ê±¸ëŸ¬??                    for idx in sorted(list(set(indices))):
                        if 0 <= idx < len(candidates):
                            global_relevant_entries.append(candidates[idx])
                                
            except Exception as e:
                print(f"   ? ï¸ AI ?„í„°ë§?ì¤??ëŸ¬ ë°œìƒ: {e}")

    if not global_relevant_entries:
        print("\n? ï¸ ?„ì²´ ?€?ì—???ˆë¡­ê²?ë°œê²¬???°ê? ?¼ë¬¸???†ìŠµ?ˆë‹¤. ë´‡ì„ ì¢…ë£Œ?©ë‹ˆ??")
        return

    # 2?¨ê³„: ê±¸ëŸ¬ì§??¼ë¬¸?¤ì— ?€???ì„¸ ?‰ê? ë°??ìˆ˜ ë§¤ê¸°ê¸?ì§„í–‰
    print(f"\n=====================================")
    print(f"?¤– ì´?{len(global_relevant_entries)}ê°œì˜ ?°ê? ?¼ë¬¸???€???¬ì¸µ ?‰ê?ë¥??œì‘?©ë‹ˆ??..")
    
    scored_papers = []

    for entry in global_relevant_entries:
        title = entry.title
        link = entry.link
        abstract = entry.description if hasattr(entry, 'description') else "ì´ˆë¡ ?†ìŒ"

        print(f"\n?“„ ?‰ê? ì¤? {title}")

        prompt = f"""
        ?ˆëŠ” ë©´ì—­?? ë¶„ì?ë¬¼???°êµ¬?ë? ?„í•œ 'ë§¤ìš° ?„ê²©?? ?„ë¬¸ ?™ìˆ  ë¹„ì„œ?´ì ë¦¬ë·°???˜ì????„ë¬¸ê°€??
        ??ëª©í‘œ??ë§¤ì¼ ìµœê³ ???„ë¦¬?°ë? ê°€ì§??¼ë¬¸ 3?¸ë§Œ ?„ì„ ?´ì„œ ?´ìŠ¤?ˆí„°ë¡??½ëŠ” ê²ƒì´??
        ?„ë˜ ?¼ë¬¸???œëª©ê³?ì´ˆë¡???½ê³ , ??ê´€?¬ì‚¬({', '.join(USER_INTERESTS)})?€???°ê???ë°??™ìˆ ???Œê¸‰?¥ì„ ë§¤ìš° ê¹ê¹?˜ê²Œ ?‰ê??´ì¤˜.
        ?¹íˆ ê¸°ì¡´ ?°êµ¬?€ ì°¨ë³„?”ë˜??ì°¸ì‹ ??Novelty)?´ë‚˜ ?™ê³„??ë¯¸ì¹  ?í–¥(Impact)????œ¼ë©?ê°€ì°¨ì—†????? ?ìˆ˜ë¥?ì¤˜ì•¼?? (?¼ë°˜?ì¸ ?¼ë¬¸?€ 4~6?? ?•ë§ ?½ì–´ë³?ê°€ì¹˜ê? ?ˆëŠ” ?°ì–´???¼ë¬¸ë§?7???´ìƒ??ì¤?.

        ?¼ë¬¸ ?œëª©: {title}
        ì´ˆë¡: {abstract}

        ë°˜ë“œ???„ë˜ ?‘ì‹??ë§ì¶°???µë???
        [?ìˆ˜] (1ë¶€??10ê¹Œì? ?«ìë§?
        [?œì¤„?”ì•½] (???¼ë¬¸??ê¼??½ì–´???˜ëŠ” ?´ìœ ë¥??¬í•¨?˜ì—¬ ?œêµ­?´ë¡œ 1~2ë¬¸ì¥ ?”ì•½)
        [?ì„¸ë¶„ì„] 1. ?µì‹¬ ë°œê²¬ê³?ì°¸ì‹ ??(Key Findings & Novelty)
        2. ?°êµ¬???Œê¸‰??(Significance & Impact)
        3. ?¤í—˜ ë°©ë²•ë¡ ì˜ ?¹ì´??(Methods)
        4. ?œê³„??(Limitations)
        ??4ê°€ì§€ ì¹´í…Œê³ ë¦¬ë¥??œìš©???´ìŠ¤?ˆí„°ì²˜ëŸ¼ ?½ê¸° ?½ê³  ?¥ë?ë¡?²Œ, ?˜ì?ë§??„ë¬¸?±ì„ ?ƒì? ?Šê³  500???´ë‚´ë¡??”ì•½?´ì¤˜. ê¸°ì¡´???†ë˜ ê´€?ì´???Œë???ë°œê²¬?€ ?´ëª¨ì§€???œê°?ìœ¼ë¡??‹ë³´?´ê²Œ ê°•ì¡°?´ì¤˜.
        """

        try:
            # ?‰ê? ?„ë£Œ ??ë°”ë¡œ ?‰ê? ëª©ë¡ ?Œì¼???€?¥í•©?ˆë‹¤. (?ìˆ˜?€ ë¬´ê??˜ê²Œ ???´ìƒ ê²€? í•˜ì§€ ?Šë„ë¡?
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(link + "\n")
            evaluated_links.add(link)

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            result_text = response.text

            if "[?ìˆ˜]" in result_text and "[?œì¤„?”ì•½]" in result_text:
                score_str = result_text.split("[?ìˆ˜]")[1].split("[?œì¤„?”ì•½]")[0].strip()
                score = int(score_str)
                short_summary = result_text.split("[?œì¤„?”ì•½]")[1].split("[?ì„¸ë¶„ì„]")[0].strip()
                detail_summary = result_text.split("[?ì„¸ë¶„ì„]")[1].strip()

                print(f"â­?AI ?‰ê? ?ìˆ˜: {score} / 10??)
                
                scored_papers.append({
                    "score": score,
                    "title": title,
                    "link": link,
                    "short_summary": short_summary,
                    "detail_summary": detail_summary
                })
            else:
                print("? ï¸ AIê°€ ?•í•´ì§??‘ì‹?€ë¡??µë??˜ì? ?Šì•˜?µë‹ˆ??")

        except Exception as e:
            print(f"? ï¸ ?ëŸ¬ ë°œìƒ: {e}")
        
        time.sleep(15) 

    # 3?¨ê³„: ?ìˆ˜ ?œìœ¼ë¡??•ë ¬ ??ìµœìƒ??3ê°??¼ë¬¸ë§?? ë³„?˜ì—¬ ?¸ì…˜ ?…ë¡œ??    if not scored_papers:
        print("\n? ï¸ ìµœì¢…?ìœ¼ë¡??•ìƒ ?‰ê????¼ë¬¸???†ìŠµ?ˆë‹¤.")
        return

    scored_papers.sort(key=lambda x: x["score"], reverse=True)
    top_3_papers = scored_papers[:3]

    print(f"\n=====================================")
    print(f"?† ?„ì²´ ?€?ì—??ê°€???’ì? ?ìˆ˜ë¥?ë°›ì? Top {len(top_3_papers)} ?¼ë¬¸??? ë³„?ˆìŠµ?ˆë‹¤!")
    print("?¸ì…˜???€?¥ì„ ?œì‘?©ë‹ˆ??..")

    today = datetime.now().strftime("%Y-%m-%d")

    for paper in top_3_papers:
        try:
            notion.pages.create(
                parent={"database_id": NOTION_DATABASE_ID},
                properties={
                    "?¼ë¬¸ ?œëª©": {"title": [{"text": {"content": paper["title"]}}]},
                    "?½ì? ? ì§œ": {"date": {"start": today}},
                    "?µì‹¬ ?”ì•½": {"rich_text": [{"text": {"content": paper["short_summary"]}}]},
                    "URL": {"url": paper["link"]}
                },
                children=[
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": f"â­??ìˆ˜: {paper['score']}/10\n\n?¤– AI ?ì„¸ ë¶„ì„:\n" + paper['detail_summary']}}]}
                    }
                ]
            )
            print(f"?‰ ?€???„ë£Œ: {paper['title']} ({paper['score']}??")
        except Exception as e:
            print(f"? ï¸ ?¸ì…˜ ?€???ëŸ¬: {e}")

if __name__ == "__main__":
    run_paper_bot()”ì•½]")[1].split("[?ì„¸ë¶„ì„]")[0].strip()
                    detail_summary = result_text.split("[?ì„¸ë¶„ì„]")[1].strip()

                    print(f"â­?AI ?‰ê? ?ìˆ˜: {score} / 10??)

                    if score >= 7:
                        print("??ê´€???¼ë¬¸?¼ë¡œ ?ì •! ?¸ì…˜???€?¥í•©?ˆë‹¤...")
                        today = datetime.now().strftime("%Y-%m-%d")

                        notion.pages.create(
                            parent={"database_id": NOTION_DATABASE_ID},
                            properties={
                                "?¼ë¬¸ ?œëª©": {"title": [{"text": {"content": title}}]},
                                "?½ì? ? ì§œ": {"date": {"start": today}},
                                "?µì‹¬ ?”ì•½": {"rich_text": [{"text": {"content": short_summary}}]},
                                "URL": {"url": link}
                            },
                            children=[
                                {
                                    "object": "block",
                                    "type": "paragraph",
                                    "paragraph": {"rich_text": [{"text": {"content": "?¤– AI ?ì„¸ ë¶„ì„:\n" + detail_summary}}]}
                                }
                            ]
                        )
                        print("?‰ ?¸ì…˜ ?€???„ë£Œ!")
                    else:
                        print("???ìˆ˜ê°€ ??•„ ?¨ìŠ¤?©ë‹ˆ??")
                else:
                    print("? ï¸ AIê°€ ?•í•´ì§??‘ì‹?€ë¡??µë??˜ì? ?Šì•˜?µë‹ˆ??")

                # ?•ìƒ?ìœ¼ë¡??‰ê?ë¥?ë§ˆì¹œ ?¼ë¬¸?€ ?¤ìŒ ë²ˆì— ?¤ì‹œ ?½ì? ?Šë„ë¡??ìŠ¤???Œì¼???”ì•½ ë§í¬ ê¸°ë¡
                with open(history_file, "a", encoding="utf-8") as f:
                    f.write(link + "\n")
                evaluated_links.add(link)

            except Exception as e:
                print(f"? ï¸ ?ëŸ¬ ë°œìƒ: {e}")
            
            time.sleep(15) 

if __name__ == "__main__":
    run_paper_bot()
