#!/usr/bin/env python3
"""Fetch max ratings server-side (no CORS) and write ratings.json.
A site that fails keeps its previous value instead of being overwritten."""
import json, re, datetime, urllib.request

USERS = {"codeforces": "siam-35862", "codechef": "siam35862",
         "atcoder": "siam35862", "leetcode": "siam35862"}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def get(url, data=None, headers=None):
    h = {"User-Agent": UA, **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def codeforces(u):
    r = json.loads(get(f"https://codeforces.com/api/user.info?handles={u}"))["result"][0]
    return {"max": r["maxRating"], "rank": r["maxRank"]}


def atcoder(u):
    h = [c for c in json.loads(get(f"https://atcoder.jp/users/{u}/history/json")) if c["IsRated"]]
    return {"max": max(c["NewRating"] for c in h)}


def codechef(u):
    m = re.search(r"Highest Rating\s*:?\s*(\d{3,4})", get(f"https://www.codechef.com/users/{u}"), re.I)
    return {"max": int(m.group(1))}


def leetcode(u):
    q = {"query": "query($u:String!){userContestRankingHistory(username:$u){attended rating}}",
         "variables": {"u": u}}
    d = json.loads(get("https://leetcode.com/graphql", json.dumps(q).encode(),
                       {"Content-Type": "application/json", "Referer": "https://leetcode.com"}))
    h = [c["rating"] for c in d["data"]["userContestRankingHistory"] if c["attended"]]
    return {"max": round(max(h))}


FETCHERS = {"codeforces": codeforces, "codechef": codechef, "atcoder": atcoder, "leetcode": leetcode}

try:
    out = json.load(open("ratings.json"))
except Exception:
    out = {}
for site, fn in FETCHERS.items():
    try:
        out[site] = fn(USERS[site])
        print("ok  ", site, out[site])
    except Exception as e:
        print("FAIL", site, e)
        out.setdefault(site, None)
out["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
json.dump(out, open("ratings.json", "w"), indent=2)
