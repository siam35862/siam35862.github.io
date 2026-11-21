#!/usr/bin/env python3
"""Fetch max rating, problems solved and contests attended server-side (no CORS)
and write ratings.json. A value that can't be fetched keeps its previous value."""
import json, re, datetime, urllib.request

USERS = {"codeforces": "siam-35862", "codechef": "siam35862",
         "atcoder": "siam35862", "leetcode": "siam35862"}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def get(url, data=None, headers=None):
    h = {"User-Agent": UA, **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def codeforces(u):
    base = "https://codeforces.com/api/"
    info = json.loads(get(base + f"user.info?handles={u}"))["result"][0]
    rating = json.loads(get(base + f"user.rating?handle={u}"))["result"]
    status = json.loads(get(base + f"user.status?handle={u}"))["result"]
    solved = {(s["problem"].get("contestId"), s["problem"]["index"]) for s in status
              if s.get("verdict") == "OK"}
    return {"max": info["maxRating"], "rank": info["maxRank"],
            "solved": len(solved), "contests": len(rating)}


def atcoder(u):
    hist = json.loads(get(f"https://atcoder.jp/users/{u}/history/json"))
    rated = [c["NewRating"] for c in hist if c["IsRated"]]
    out = {"max": max(rated) if rated else None, "contests": len(hist)}
    try:
        out["solved"] = json.loads(get(f"https://kenkoooo.com/atcoder/atcoder-api/v3/user/ac_rank?user={u}"))["count"]
    except Exception as e:
        print("  atcoder solved count failed:", e)
    return out


def codechef(u):
    html = get(f"https://www.codechef.com/users/{u}")

    def grab(pattern):
        m = re.search(pattern, html, re.I)
        return int(m.group(1)) if m else None

    return {"max": grab(r"Highest Rating\s*:?\s*(\d{3,4})"),
            "solved": grab(r"Total Problems Solved\s*:?\s*(\d+)"),
            "contests": grab(r"Contests? Participated\s*:?\s*(?:<[^>]*>\s*)*(\d+)")}


def leetcode(u):
    q = {"query": "query($u:String!){matchedUser(username:$u){submitStatisticsGlobal{acSubmissionNum{difficulty count}}} "
                  "userContestRanking(username:$u){attendedContestsCount} "
                  "userContestRankingHistory(username:$u){attended rating}}",
         "variables": {"u": u}}
    d = json.loads(get("https://leetcode.com/graphql", json.dumps(q).encode(),
                       {"Content-Type": "application/json", "Referer": "https://leetcode.com"}))["data"]
    hist = [c["rating"] for c in (d["userContestRankingHistory"] or []) if c["attended"]]
    stats = (d["matchedUser"] or {}).get("submitStatisticsGlobal", {}).get("acSubmissionNum", [])
    solved = next((x["count"] for x in stats if x["difficulty"] == "All"), None)
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
