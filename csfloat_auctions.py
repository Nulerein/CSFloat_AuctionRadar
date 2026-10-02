#!/usr/bin/env python3
"""
CSFloat: soon-to-end auctions sorted by discount.

How it works:
  1. Fetches auctions (type=auction) up to --max-price, sorted by "Expires Soon".
  2. Keeps auctions ending within the next --hours hours.
  3. Calculates the discount by comparing the next bid with the CSFloat reference price.
  4. Prints the top deals with links.

Install:    pip install requests
API key:    csfloat.com/profile -> Developer tab (keep it private)
Run:        python csfloat_auctions.py --max-price 30 --hours 12 --top 15
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

API = "https://csfloat.com/api/v1/listings"
ITEM_URL = "https://csfloat.com/item/{}"


def parse_time(s):
    """Convert an ISO timestamp from the API to a UTC datetime, or return None if invalid."""
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    m = re.match(r"(.*?\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$", s)
    if m:  # Normalize fractional seconds to six digits for compatibility across Python versions.
        head, frac, tail = m.groups()
        s = head + (frac or ".0")[:7].ljust(7, "0") + tail
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get(session, params, retries=3):
    for _ in range(retries):
        r = session.get(API, params=params, timeout=20)
        if r.status_code == 429:
            try:
                wait = int(r.headers.get("Retry-After", 10))
            except ValueError:
                wait = 10
            print(f"429 Too Many Requests; retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        if r.status_code in (401, 403):
            sys.exit(f"Error {r.status_code}: check your API key (--key or the CSFLOAT_API_KEY environment variable).")
        r.raise_for_status()
        return r.json()
    sys.exit("Too many requests (429). Wait a bit or reduce --pages.")


def unpack(payload):
    """The API returns either a list or {"data": [...], "cursor": "..."}."""
    if isinstance(payload, list):
        return payload, None
    return (payload.get("data") or payload.get("listings") or []), payload.get("cursor")


def ref_price(listing):
    """Return the reference price in cents and its source: 'ref' (CSFloat) or 'steam' (fallback)."""
    ref = listing.get("reference") or {}
    for key in ("predicted_price", "base_price"):
        if ref.get(key):
            return ref[key], "ref"
    scm = (listing.get("item") or {}).get("scm") or {}
    if scm.get("price"):
        return scm["price"], "steam"
    return None, None


def fetch(session, args):
    """Return (listing, expiration time) pairs for auctions ending within --hours."""
    params = {
        "type": "auction",
        "sort_by": "expires_soon",
        "max_price": int(round(args.max_price * 100)),  # The API expects prices in cents.
        "limit": 50,
    }
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=args.hours)
    found, no_exp, cursor = [], 0, None
    for page in range(args.pages):
        if cursor:
            params["cursor"] = cursor
        batch, cursor = unpack(get(session, params))
        if not batch:
            break
        if args.debug and page == 0:
            print(json.dumps(batch[0], indent=2, ensure_ascii=False))
        for lot in batch:
            if lot.get("state", "listed") != "listed":
                continue
            exp = parse_time((lot.get("auction_details") or {}).get("expires_at"))
            if exp is None:
                no_exp += 1
                continue
            if exp <= now:
                continue
            if exp > deadline:
                return found, no_exp  # Results are sorted by expiration, so later pages are also later.
            found.append((lot, exp))
        if not cursor:
            break
    return found, no_exp


def fmt_left(exp):
    secs = max(int((exp - datetime.now(timezone.utc)).total_seconds()), 0)
    h, m = divmod(secs // 60, 60)
    return f"{h}h {m:02d}m"


def main():
    ap = argparse.ArgumentParser(description="CSFloat: soon-to-end auctions ranked by discount")
    ap.add_argument("--max-price", type=float, default=50, help="maximum price in $ (default: 50)")
    ap.add_argument("--hours", type=float, default=24, help="include auctions ending within N hours (default: 24)")
    ap.add_argument("--min-discount", type=float, default=0,
                    help="minimum discount in percent (default: 0; use -100 to show all)")
    ap.add_argument("--top", type=int, default=20, help="number of results to show (default: 20)")
    ap.add_argument("--pages", type=int, default=6, help="number of pages to scan (50 listings per page)")
    ap.add_argument("--key", default=os.getenv("CSFLOAT_API_KEY"),
                    help="API key (or set the CSFLOAT_API_KEY environment variable)")
    ap.add_argument("--debug", action="store_true", help="print the raw JSON for the first listing")
    args = ap.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "csfloat-auctions-script/1.0"
    if args.key:
        session.headers["Authorization"] = args.key

    found, no_exp = fetch(session, args)

    rows, no_ref = [], 0
    for lot, exp in found:
        item = lot.get("item") or {}
        details = lot.get("auction_details") or {}
        bid = details.get("min_next_bid") or lot.get("price") or 0  # Minimum bid required now.
        ref, src = ref_price(lot)
        if not ref:
            no_ref += 1
            continue
        disc = (ref - bid) / ref * 100
        if disc < args.min_discount:
            continue
        rows.append({
            "id": lot.get("id"), "exp": exp, "bid": bid, "ref": ref, "src": src, "disc": disc,
            "float": item.get("float_value"), "name": item.get("market_hash_name", "?"),
        })
    rows.sort(key=lambda r: r["disc"], reverse=True)

    if not rows:
        print("No results found. Try increasing --max-price or --hours, or lowering --min-discount.")
        if no_exp:
            print(f"{no_exp} listings have no expires_at: run with --debug and check the field names.")
        if no_ref:
            print(f"{no_ref} listings have no reference price.")
        return

    shown = rows[: args.top]
    print(f"Found {len(rows)}; showing {len(shown)} (up to ${args.max_price:g}, ending within {args.hours:g}h)\n")
    for i, r in enumerate(shown, 1):
        fv = f"{r['float']:.4f}" if r["float"] is not None else "-"
        mark = " *" if r["src"] != "ref" else ""
        print(f"{i:>2}. {r['disc']:+6.1f}%  bid ${r['bid'] / 100:>7.2f}  ref ${r['ref'] / 100:>7.2f}{mark}  "
              f"{fmt_left(r['exp']):>8}  float {fv}  {r['name']}")
        print(f"     {ITEM_URL.format(r['id'])}")
    if any(r["src"] != "ref" for r in shown):
        print("\n* CSFloat reference unavailable; compared with the Steam price (discount may be overstated)")


if __name__ == "__main__":
    main()
