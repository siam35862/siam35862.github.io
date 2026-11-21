#!/usr/bin/env python3
"""Fetch max rating, problems solved and contests attended server-side (no CORS)
and write ratings.json. A value that can't be fetched keeps its previous value."""
import json, re, datetime, urllib.request
from urllib.parse import quote

USERS = {"codeforces": "siam-35862", "codechef": "siam35862",
         "atcoder": "siam35862", "leetcode": "siam35862"}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def get(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def codeforces(u):
    base = "https://codeforces.com/api/"
    info = json.loads(get(base + f"user.info?handles={u}"))["result"][0]
    rating = json.loads(get(base + f"user.rating?handle={u}"))["result"]
    status = json.loads(get(base + f"user.status?handle={u}"))["result"]
    solved = {(s["problem"].get("contestId") or s["problem"].get("problemsetName"), s["problem"]["index"])
              for s in status if s.get("verdict") == "OK"}
    count = len(solved)
    try:  # the profile page also counts solves the API can't see (e.g. private groups)
        html = get(f"https://codeforces.com/profile/{u}")
        m = re.search(r"([\d,]+)\s+problems?\s*</div>\s*<div[^>]*>\s*solved for all time", html, re.I)
        if m:
            count = max(count, int(m.group(1).replace(",", "")))
    except Exception as e:
        print("  codeforces profile page failed:", e)
    return {"max": info["maxRating"], "rank": info["maxRank"],
            "solved": count, "contests": len(rating)}


def atcoder(u):
    hist = json.loads(get(f"https://atcoder.jp/users/{u}/history/json"))
    rated = [c["NewRating"] for c in hist if c["IsRated"]]
    out = {"max": max(rated) if rated else None, "contests": len(hist)}
    try:
        out["solved"] = json.loads(get(f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/ac_rank?user={u}"))["count"]
    except Exception as e:
        print("  atcoder solved count failed:", e)
    return out


def browser_html(url):
    """Last resort: load the page in a real headless Chromium (needs playwright)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        html = page.content() + "\n" + page.inner_text("body")
        browser.close()
    return html


def fetch_profile_html(url):
    """CodeChef may block datacenter IPs, so try direct, then public proxies, then a real browser."""
    last = None
    for u in (url, "https://corsproxy.io/?url=" + quote(url, safe=""),
              "https://api.allorigins.win/raw?url=" + quote(url, safe="")):
        try:
            html = get(u, headers={"Accept": "text/html,application/xhtml+xml"})
            if "Total Problems Solved" in html or "Highest Rating" in html:
                return html
            last = Exception("page loaded but no stats in it (blocked?)")
        except Exception as e:
            last = e
        print("  codechef source failed:", last)
    try:
        html = browser_html(url)
        if "Total Problems Solved" in html or "Highest Rating" in html:
            return html
        last = Exception("browser loaded the page but no stats in it")
    except Exception as e:
        last = e
    raise last


def codechef(u):
    html = fetch_profile_html(f"https://www.codechef.com/users/{u}")

    def grab(*patterns):
        for p in patterns:
            m = re.search(p, html, re.I)
            if m:
                return int(m.group(1))
        return None

    return {"max": grab(r"Highest Rating\s*:?\s*(\d{3,4})"),
            "solved": grab(r"Total Problems Solved\s*:?\s*(?:<[^>]*>\s*)*(\d+)"),
            "contests": grab(r"Contests\s*\((\d+)\)", r"Contests? Participated\s*:?\s*(?:<[^>]*>\s*)*(\d+)")}


def leetcode(u):
    q = {"query": "query($u:String!){matchedUser(username:$u){submitStatisticsGlobal{acSubmissionNum{difficulty count}}} "
                  "userContestRanking(username:$u){attendedContestsCount} "
                  "userContestRankingHistory(username:$u){attended rating}}",
         "variables": {"u": u}}
    d = json.loads(get("https://leetcode.com/graphql", json.dumps(q).encode(),
                       {"Content-Type": "application/json", "Referer": "https://leetcode.com"}))["data"]
    hist = [c["rating"] for c in (d["userContestRankingHistory"] or []) if c["attended"]]
    stats = ((d.get("matchedUser") or {}).get("submitStatisticsGlobal") or {}).get("acSubmissionNum", [])
    solved = next((x["count"] for x in stats if x["difficulty"] == "All"), None)
    if solved is None:
        try:
            solved = json.loads(get(f"https://leetcode-api-faisalshohag.vercel.app/{u}")).get("totalSolved")
        except Exception as e:
            print("  leetcode solved fallback failed:", e)
    ranking = d.get("userContestRanking") or {}
    return {"max": round(max(hist)) if hist else None, "solved": solved,
            "contests": ranking.get("attendedContestsCount", len(hist) or None)}


FETCHERS = {"codeforces": codeforces, "codechef": codechef, "atcoder": atcoder, "leetcode": leetcode}

try:
    out = json.load(open("ratings.json"))
except Exception:
    out = {}
for site, fn in FETCHERS.items():
    try:
        new = {k: v for k, v in fn(USERS[site]).items() if v is not None}
        out[site] = {**(out.get(site) or {}), **new}
        print("ok  ", site, out[site])
    except Exception as e:
        print("FAIL", site, e)
        out.setdefault(site, None)
out["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
json.dump(out, open("ratings.json", "w"), indent=2)
