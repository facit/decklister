#!/usr/bin/env python3
"""
Diagnostic (read-only, no manifest written). Dumps the foil-relevant fields the SWU API returns for
cards in a set, so we can see what actually distinguishes a fixed-finish printing (non-foil prestige,
JTL standard non-foil) from a genuinely loose standard card — BEFORE changing _resolve_foil.

For each matching card it prints: SET/number, variant label, variantTypes[].foil, whether it's a
variant (variantOf set), and EVERY key anywhere in the record whose name mentions "foil" with its
value. That last part reveals whether a `hasFoil`-style flag exists and is the real signal.

Usage:
  python3 diagnose_foil.py --set LOF
  python3 diagnose_foil.py --set LOF --name prestige      # filter by name/subtitle/label substring
  python3 diagnose_foil.py --set JTL --number 1           # one number (all its printings)
"""

import argparse
import json

import swuscan_manifest as idl


def foil_keys(node, path=""):
    """Recursively collect (dotted-path, value) for every key containing 'foil'."""
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}.{k}" if path else k
            if "foil" in str(k).lower() and not isinstance(v, (dict, list)):
                found.append((here, v))
            found += foil_keys(v, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += foil_keys(v, f"{path}[{i}]")
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="set_code", required=True, help="set code, e.g. LOF")
    ap.add_argument("--name", help="substring filter on name/subtitle/variant label (case-insensitive)")
    ap.add_argument("--number", help="exact card number filter")
    args = ap.parse_args()

    want_set = args.set_code.upper()
    name_q = (args.name or "").lower()

    session = idl.requests.Session()
    session.headers.update(idl.API_HEADERS)

    page, total_pages, shown = 1, None, 0
    while True:
        params = {"locale": "en", "pagination[page]": page,
                  "pagination[pageSize]": idl.PAGE_SIZE, "populate": "*"}
        resp = idl._get_with_retries(session, idl.CARD_LIST_ENDPOINT, params=params)
        data = resp.json()
        if total_pages is None:
            total_pages = data.get("meta", {}).get("pagination", {}).get("pageCount", 1)

        for entry in data.get("data", []):
            attrs = entry.get("attributes", entry)
            expansion = idl._unwrap(attrs.get("expansion")) or {}
            if (expansion.get("code") or "").upper() != want_set:
                continue
            number = attrs.get("cardNumber")
            if args.number and str(number) != str(args.number):
                continue

            vts = idl._rel_list(attrs.get("variantTypes"))
            vt = vts[0] if vts else {}
            label = vt.get("name")
            name = attrs.get("title") or ""
            subtitle = attrs.get("subtitle") or ""
            if name_q and name_q not in f"{name} {subtitle} {label}".lower():
                continue

            is_variant = bool(idl._unwrap(attrs.get("variantOf")))
            print(f"\n{want_set}/{number}  {name}{' - ' + subtitle if subtitle else ''}")
            print(f"  variant_label : {label!r}")
            print(f"  vt.foil       : {vt.get('foil')!r}")
            print(f"  is_variant    : {is_variant}  (variantOf set)")
            if len(vts) > 1:
                print(f"  NOTE: {len(vts)} variantTypes on this record: "
                      f"{[ (v.get('name'), v.get('foil')) for v in vts ]}")
            fk = foil_keys(attrs)
            print(f"  all foil-ish keys: {fk if fk else 'NONE'}")
            shown += 1

        if page >= (total_pages or 1):
            break
        page += 1

    print(f"\n{shown} card(s) shown.")
    if not shown:
        print("No matches — check the set code and filters.")


if __name__ == "__main__":
    main()
