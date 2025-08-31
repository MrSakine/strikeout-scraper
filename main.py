import requests
import logging
import random
import time
from bs4 import BeautifulSoup
from datetime import datetime
from collections import defaultdict
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)
log_format = (
    "[%(name)s-%(levelname)s] "
    "%(asctime)s - %(message)s"
)

logging.basicConfig(level=logging.INFO, format=log_format)

SPORTS_MAP = {
    "soccer": {
        "epl": "Premier League",
        "liga": "La Liga",
        "la-liga": "La Liga",
        "bundesliga": "Bundesliga",
        "ligue-1": "Ligue 1",
        "russia-premier-league": "Premier League Russian",
        "portugal-primera-liga": "Portugal liga",
        "portugal-segunda-liga": "Portugal liga",
        "south-africa-psl": "South Africa PSL",
        "spl": "Scottish Premiership",
        "africa-cup-of-nations": "CAN",
        "eredivisie": "Eredivisie",
        "austria-bundesliga": "Austria Bundesliga",
        "serie-a": "Serie A",
        "argentina-primera": "Argentina Primera",
        "turkey-super-lig": "Turkey Super Lig",
        "brasil-serie-a": "Brazil Serie A",
        "usa-open-cup": "USA OPEN CUP",
        "champions-league": "Champions League",
        "carabao-cup": "Carabao Cup",
        "dfb-pokal": "DFB Pokal",
    },
    "basketball": {
        "nba": "NBA",
        "wnba": "WNBA",
        "africa-bal": "Basketball Africa League (BAL)",
        "fiba": "FIBA",
    }
}

SPORTS = ["soccer", "basketball"]


def load_proxies(type: str = "http"):
    """
    Load a list of proxies from a remote source.
    """
    try:
        url = f"https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/{type}/data.txt"
        res = []
        response = requests.get(url)
        if response.status_code == 200:
            res = response.text.splitlines()

        logger.info(f"Loaded {len(res)} proxies from {url}")
        return res
    except Exception as e:
        logger.error(f"Error loading proxies: {e}")
        return []


def fetch_live_matches(sport="soccer", proxies_list=None, max_retries=10):
    """
    Fetch live matches for a specific sport.
    """
    url = f"https://strikeout.im/{sport}"
    headers = {"User-Agent": UserAgent().random}

    if not proxies_list:
        proxies_list = [None]
    last_exception = None
    for attempt in range(1, max_retries + 1):
        chosen = random.choice(proxies_list)
        proxy = {"http": chosen, "https": chosen} if chosen else None
        logger.info("Attempt %d: Fetching %s using proxy: %s",
                    attempt, url, chosen)
        try:
            resp = requests.get(url, headers=headers,
                                proxies=proxy, timeout=10, verify=True)
            resp.raise_for_status()
            logger.info("Success with proxy: %s", chosen)
            break
        except Exception as e:
            last_exception = e
            logger.warning("Proxy %s failed: %s", chosen, e)
            time.sleep(0.5)
    else:
        logger.error("All proxies failed")
        raise last_exception

    soup = BeautifulSoup(resp.text, "html.parser")
    # print(soup.prettify())

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()
    results = defaultdict(list)

    for a in soup.select("a.btn.btn-primary.text-orange"):  # only live matches
        href = a.get("href", "")
        title = a.get("title", "").strip()

        # detect league
        league = None
        for key, name in SPORTS_MAP[sport].items():
            if f"/{key}/" in href:
                league = name
                break
        if not league:
            continue

        # only keep real matches (must contain "vs")
        if "vs" not in title:
            continue

        # extract time from <span content="...">
        time_span = a.find("span", {"content": True})
        if time_span and time_span.has_attr("content"):
            try:
                match_time = datetime.fromisoformat(time_span["content"])
                if match_time < now:  # skip if match already started/past
                    continue
                hour = match_time.strftime("%H:%M")
            except ValueError:
                hour = "??:??"
        else:
            hour = "??:??"

        logger.info("Match title: %s", title)
        logger.info("Match league: %s", league)

        # extract time
        time_span = a.find("span", {"content": True})
        hour = time_span.get_text(strip=True) if time_span else "??:??"

        link = "https://strikeout.im" + href if href else "pas encore de lien"

        logger.info("Appending to results...")
        results[league].append({
            "date": today,
            "hour": hour,
            "teams": title,
            "link": link,
        })

    logger.info("All league results: %s", results.items())

    return today, results


if __name__ == "__main__":
    proxies = load_proxies("socks4")
    for sport in SPORTS:
        date, matches_by_league = fetch_live_matches(sport=sport)
        print(f"Live matches for {date}: {matches_by_league.values()}")
        for league, games in matches_by_league.items():
            print(f"{date} - {league}")
            for match in games:
                print(f"{match['hour']} {match['teams']}")
                print(match['link'], end="\n\n")
            print()
