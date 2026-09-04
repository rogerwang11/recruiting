# xhire

Finds X posts from brands hiring UGC creators, scores them, and renders the good
ones as an HTML page. Built around a hard client-side spend cap, because the X
API bills per post returned.

## 1. Get an API key

1. Go to **https://developer.x.com** and sign in with the X account you want the
   app to belong to.
2. Create a **Project**, then an **App** inside it. Search only works for apps
   attached to a project.
3. Open the app's **Keys and tokens** tab and generate the **Bearer Token**.
   That single token is all this tool needs — it only reads public posts, so the
   OAuth 1.0a consumer keys and access tokens are not required.
4. In **Billing**, add a payment method and buy credits. There is no free tier
   any more; requests fail with 403 until the project has credits.

Copy the token into `.env` at the repo root:

```
X_BEARER_TOKEN=AAAAAAAAAA...
```

`.env` is gitignored. Never commit the token — anyone with it can spend your
credits.

## 2. Configure

```bash
cp config.example.toml config.toml
pip install -r requirements.txt
```

Edit `config.toml` to set your caps and queries. The defaults target UGC creator
hiring posts and cap spend at $25/month.

## 3. Put a cap on spend

Set the cap in **both** places, so a bug in one can't drain the other.

**In the X developer console** — this is the only cap X itself enforces:

- **Billing → Spending limit**: sets a ceiling per billing cycle. Requests stop
  when it's hit.
- **Auto-recharge**: leave it **off** while you're testing. It tops up your
  balance automatically when it runs low, which defeats the purpose of a cap. If
  you do enable it, note it fires at most once per 5 minutes.
- Buy a small amount of credits to start ($5–10). An empty balance is the
  hardest cap there is.

**In `config.toml`** — enforced by this tool before each request:

```toml
[budget]
monthly_usd = 25.00   # refuses any request that could exceed this
per_run_usd = 1.00    # and any single run that could exceed this
```

The guard reserves the *worst case* (a full page, `max_results × $0.005`) before
each request goes out, then records what it actually cost. So a request already
in flight can never push you past the cap. Spend is tracked in the `usage` table
in SQLite, per request, and survives crashes.

Check where you stand any time — this makes no API calls:

```bash
python -m xhire status
python -m xhire estimate   # cost projection for your current config
```

## 4. Run it

```bash
python -m xhire poll      # fetches new posts. this is the part that costs money
python -m xhire report    # builds reports/leads.html
open reports/leads.html
```

`poll` prints what each page cost as it goes:

```
[ugc-direct-ask]
  resuming after post 1800000000000000042
  page 1: 23 posts, $0.115
    4 likely hiring, 19 filtered out
```

Each query stores a cursor (`since_id`), so the next poll only fetches posts you
haven't seen. You never pay twice for the same post.

## Where you see the posts

`python -m xhire report` writes `reports/leads.html` — a standalone page, sorted
by score, with a link to each post and the reasons it scored the way it did. Open
it in a browser. Everything is also in `posts.db` (SQLite) if you'd rather query
it directly:

```sql
SELECT author_handle, score, text, url FROM posts
WHERE verdict = 'likely_hiring' ORDER BY created_at DESC;
```

## How scoring works

The hard part in this niche isn't finding posts about UGC — it's telling apart
the brand hiring a creator from the creator advertising themselves. Both use the
same words. "UGC creator" appears in *"looking for a UGC creator"* and in *"I'm a
UGC creator, DM for rates"*, and there are far more of the second kind.

So `classify.py` scores direction, not topic:

- **Demand language** (`we're hiring`, `creators wanted`, `open call`) scores up.
- **Supply language** (`my rates`, `available for work`, `I'm a UGC creator`)
  scores down, hard enough to sink a post that also contains a demand phrase.
- **Quality signals** (`paid`, a dollar figure, `budget`) only apply to a post
  that already reads as demand — otherwise they'd promote a creator's rate card.

Anything scoring 5+ is `likely_hiring`, 2–4 is `maybe_hiring`. Tune the weights
in `classify.py`; `tests/test_classify.py` covers the trap cases.

## Keeping cost down

You're billed per post returned, so filtering on X's side is free and filtering
in Python is not. Push every exclusion you can into the query string:

```
-is:retweet -is:reply -"my rates" -"open to work" lang:en
```

Retweets alone are usually a third of the raw volume in this niche.

## Tests

```bash
pip install pytest && python -m pytest tests/ -q
```

23 tests, no network calls — the API is stubbed.

## Note on scraping

This uses the official API. Scraping x.com directly violates X's terms of
service, and their anti-bot measures make it unreliable regardless.
