import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import defaultdict

LEAGUES = {
    "epl": "Premier League",
    "liga": "La Liga",
    "la-liga": "La Liga",
    "bundesliga": "Bundesliga",
    "ligue-1": "Ligue 1",
    "russia-premier-league": "Premier League Russian",
    "portugal-segunda-liga": "Portugal liga",
    "south-africa-psl": "South Africa PSL",
    "spl": "Scottish Premiership",
    "africa-cup-of-nations": "CAN",
    "eredivisie": "Eredivisie",
    "austria-bundesliga": "Austria Bundesliga",
    "serie-a": "Serie A",
    "argentina-primera": "Argentina Primera",
    "turkey-super-lig": "Turkey Super Lig",
    "brasil-serie-a": "Brazil Serie A"
}

URL = "https://strikeout.im/soccer"


def fetch_live_matches():
    resp = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    print(soup.prettify())

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()
    results = defaultdict(list)

    for a in soup.select("a.btn.btn-primary.text-orange"):  # only live matches
        href = a.get("href", "")
        title = a.get("title", "").strip()

        # detect league
        league = None
        for key, name in LEAGUES.items():
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

        print("Match title: %s", title)
        print("Match league: %s", league)

        # extract time
        time_span = a.find("span", {"content": True})
        hour = time_span.get_text(strip=True) if time_span else "??:??"

        link = "https://strikeout.im" + href if href else "pas encore de lien"

        print("Appending to results...")
        results[league].append({
            "date": today,
            "hour": hour,
            "teams": title,
            "link": link,
        })

    print("All league results: %s", results.items())

    return today, results


if __name__ == "__main__":
    date, matches_by_league = fetch_live_matches()
    print(f"Live matches for {date}: {matches_by_league.values()}")
    for league, games in matches_by_league.items():
        print(f"{date} - {league}")
        for match in games:
            print(f"{match['hour']} {match['teams']}")
            print(match['link'], end="\n\n")
        print()
