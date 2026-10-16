# fibiger.org

Static homepage, hosted on GitHub Pages. Everything that gets published lives in `site/`.

```
site/index.html                 the page (HTML + CSS in one file)
site/images/                    photos
site/images/instagram/          Instagram thumbnails (managed by the script)
site/resume.pdf                 resume, linked from the top bar and Professional section
data/instagram.json             the 6 newest posts shown in the strip (managed by the script)
scripts/update_instagram.py     pulls the Behold feed and rewrites the strip
.github/workflows/deploy.yml    builds and deploys on every push, and daily
```

## Editing

Edit `site/index.html` (GitHub's web editor is fine) and commit to `main`. The workflow
deploys it within a minute or two. Every change is in git history, so rolling back is a revert.

Leave the `<!-- instagram:start -->` / `<!-- instagram:end -->` markers and everything between
them alone — the daily job rewrites that block.

## Instagram strip

Once a day (and on every push) the workflow fetches the Behold JSON feed, downloads any new
thumbnails, keeps the 6 newest posts in `data/instagram.json`, rewrites the strip, commits
the change and deploys.

Collab posts someone else authored (e.g. ones Emily posted and invited you to) never come
through Instagram's API, so they won't appear here even though they're on your grid.

- If the feed can't be fetched, the run shows a warning and the site deploys unchanged.
- A post you delete or archive on Instagram drops off the strip on the next run.
- If a scheduled run finds nothing new for ~50 days it makes an empty commit, because
  GitHub turns off schedules on public repos after 60 days without activity.

To refresh by hand: Actions → Build and deploy → Run workflow.

### One-time setup

1. Switch Instagram to a Creator account (Settings → Account type and tools).
2. At behold.so: connect the Instagram account, create a feed, choose **JSON feed**,
   and copy the feed URL (`https://feeds.behold.so/…`).
3. In this repo: Settings → Secrets and variables → Actions → New repository secret,
   name `BEHOLD_FEED_URL`, value the feed URL.
4. Actions → Build and deploy → Run workflow.

## Custom domain

Settings → Pages → Custom domain: `www.fibiger.org`, then at the DNS host:

| Name | Type | Value |
| --- | --- | --- |
| `www` | CNAME | `<your-github-username>.github.io` |
| `@` | A | `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` |
| `@` | AAAA | `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153` |

Don't touch the MX or TXT records — email for the domain depends on them. Tick
**Enforce HTTPS** on the Pages screen once the certificate is issued.
