# swudb.com Internal API

This documents the internal JSON API used by [swudb.com](https://swudb.com) — an unofficial fan
site for Star Wars: Unlimited. The API is not publicly documented but is stable enough to use as
it powers the website itself.

---

## Authentication / Headers

Requests must include a browser-like `User-Agent` or the server returns `403 Forbidden`.

```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Accept: application/json
```

No API key or login cookie is required for read-only card searches.

---

## Card Search

```
GET https://swudb.com/api/search/{query}
```

The `{query}` is a URL-encoded search string using the swudb.com search syntax (see
[swudb.com/syntax](https://swudb.com/syntax)). The query goes in the **URL path**, not as a
query parameter.

### Query parameters

| Parameter  | Required | Values                                                         | Description                          |
|------------|----------|----------------------------------------------------------------|--------------------------------------|
| `grouping` | Yes      | `cards`, `variants`, `printings`                               | How to group results                 |
| `sortorder`| Yes      | `setno`, `name`, `aspect`, `cost`, `power`, `hp`, `type`, `rarity`, `artist`, `price` | Sort field |
| `sortdir`  | Yes      | `asc`, `desc`                                                  | Sort direction                       |

Use `grouping=cards` to get one result per unique card (not one per printing or variant).

### Search syntax highlights

The full syntax is documented at [swudb.com/syntax](https://swudb.com/syntax). The most relevant
fields for card lookup:

| Field     | Example                          | Matches                        |
|-----------|----------------------------------|--------------------------------|
| (default) | `Director Krennic`               | Cards whose name contains all words |
| `title:`  | `title:"Aspiring to Authority"`  | Cards whose subtitle matches the phrase |
| `set:`    | `set:SOR`                        | Cards from a specific set      |
| `type:`   | `type:leader`                    | Cards of a specific type       |

**Important:** Hyphens in the default name search are treated as word separators, not NOT
operators. `IG-11`, `4-LOM`, and `0-0-0` all work correctly without any escaping.

**Combining name and title** to uniquely identify a card:

```
IG-11 title:"I Cannot Be Captured"
4-LOM title:"Bounty Hunter for Hire"
Director Krennic title:"Aspiring to Authority"
```

### Example request

```
GET https://swudb.com/api/search/IG-11%20title%3A%22I%20Cannot%20Be%20Captured%22?grouping=cards&sortorder=setno&sortdir=asc
```

### Response structure

```json
{
  "explanation": "where the card has <samp>ig-11</samp> in its name ...",
  "validQuery": true,
  "printings": [
    {
      "variantId": 905,
      "cardId": 291,
      "printingId": 1017,
      "expansionAbbreviation": "SHD",
      "cardNumber": "170",
      "releaseDate": "0001-01-01T00:00:00",
      "expansionType": 0,
      "cardName": "IG-11",
      "cardTitle": "I Cannot Be Captured",
      "isUnique": true,
      "cost": 7,
      "arena": 0,
      "power": 5,
      "powerBonus": null,
      "hp": 7,
      "hpBonus": null,
      "aspectIds": [2, 6],
      "frontsideAspectIds": [2, 6],
      "backsideAspectIds": [2, 6],
      "cardType": 1,
      "isToken": false,
      "variantType": 1,
      "traits": "Bounty Hunter,Droid",
      "rarity": 3,
      "artist": "...",
      "foil": false,
      "frontImagePath": "~/cards/SHD/170.png",
      "backImagePath": "",
      "isFrontPortrait": true,
      "isBackPortrait": false,
      "stamp": null,
      "lowPrice": 0.10,
      "marketPrice": 0.20,
      "tcgpUrl": "https://..."
    }
  ]
}
```

### Key response fields

| Field                   | Description                                                      |
|-------------------------|------------------------------------------------------------------|
| `validQuery`            | `false` if the query string could not be parsed                  |
| `printings`             | Array of matching cards (empty array if none found)              |
| `expansionAbbreviation` | Set code, e.g. `"SOR"`, `"SHD"`, `"LAW"`                        |
| `cardNumber`            | Zero-padded card number, e.g. `"001"`, `"170"`                   |
| `cardName`              | Card name, e.g. `"IG-11"`                                        |
| `cardTitle`             | Card subtitle, e.g. `"I Cannot Be Captured"` (empty string if none) |
| `variantType`           | `1` = Normal, `2` = Hyperspace, `3` = Showcase, `4` = Organized Play |
| `cardType`              | `0` = Leader, `1` = Unit, `2` = Event, `3` = Upgrade, `4` = Base |
| `rarity`                | `1` = Common, `2` = Uncommon, `3` = Rare, `4` = Legendary, `5` = Special |
| `arena`                 | `0` = Ground, `1` = Space                                        |
| `traits`                | Comma-separated trait list, e.g. `"Bounty Hunter,Droid"`         |
| `frontImagePath`        | Image path; replace `~` with `https://swudb.com` for full URL    |

### Image URLs

Card images are served from `https://swudb.com/cards/{SET}/{NUMBER}.png`:

```
https://swudb.com/cards/SHD/170.png       ← normal art
https://swudb.com/cards/SHD/170-h.png     ← hyperspace art (suffix -h)
https://swudb.com/cards/SOR/001-portrait.png  ← back face of double-sided card
```

The `frontImagePath` field in the response uses `~/cards/...` — replace `~` with
`https://swudb.com` to get the full URL.

---

## Single Card Page

```
GET https://swudb.com/card/{SET}/{NUMBER}
```

Loads the swudb.com card detail page (HTML, React SPA — not a JSON API).

Example: `https://swudb.com/card/SHD/170`

---

## Notes

- This is an **unofficial internal API** with no SLA or versioning guarantee. The JS bundle
  filename (e.g. `index-Dz7IiNQY.js`) changes on each deploy, but the `/api/search/` endpoint
  has been stable.
- The site blocks requests without a browser User-Agent (`403 Forbidden`).
- Rate limiting has not been observed but be considerate — use caching and avoid parallel
  floods of requests.
- `grouping=cards` returns one entry per unique card. `grouping=variants` returns one entry per
  variant (normal, hyperspace, showcase). `grouping=printings` returns one per physical printing
  (e.g. separate entries for foil vs non-foil).
