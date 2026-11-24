---
name: blog-post
description: Write a new blog post for this Jekyll/Chirpy site (d4sw4r.github.io) in the established style, optionally with a generated cover image, then build-check it and open a PR. Use when the user asks for a new Blogartikel/blog post/article, a next part of a series, or a Titelbild/cover image for a post.
---

# Blog post workflow

The site is Jekyll + Chirpy (`_config.yml`, timezone `Europe/Berlin`). Posts are in English,
even though the user usually writes to you in German. Answer the user in German.

## 1. Gather context (keep it short)

- `ls _posts` to see the latest posts and whether this continues a series
  (e.g. the Talos series: `2026-11-19-…`, `-20-…`, `-21-…`, `-25-…`).
- For a series: read the **previous part fully** (intro, final thoughts, "Next up:" teaser)
  so you can continue the story, use the same versions/names, and pay off the teaser.
- For a standalone topic: skim one or two recent posts of the same category for tone.
- If the user gave no topic, propose the natural next part (from the previous "Next up:")
  and just write it. Don't ask unless there is no sensible default.

## 2. File and front matter

Path: `_posts/YYYY-MM-DD-kebab-slug.md`. "Für morgen" means tomorrow's date.

```yaml
---
title: "Series Name – Part N: Short Punchy Subtitle"
description: "One or two sentences: what the reader gets out of it."
date: YYYY-MM-DD 08:00 +0100   # +0200 during CEST (end of March to end of October)
categories: [kubernetes, gitops]      # 1–2 lowercase, reuse existing ones
tags: [talos, kubernetes, fluxcd, …]  # 5–10 lowercase
image:
  path: /assets/img/<slug>.png
  alt: Short description of the cover
---
```

Reuse existing categories (`grep -h "^categories" _posts/*`) instead of inventing new ones.

## 3. Style (match the existing technical posts)

- Open with a recap: link the previous parts with `**[Part 1]({% post_url 2026-11-19-… %})**`,
  then state the problem this post solves in 1–2 short paragraphs.
- Add a "This part covers:" bullet list using `- 👉 **bold key term** …`.
- Use `## Step N: …` or topic `##` sections, each with a short explanation **why**,
  then complete, copy-pasteable code blocks with language tags (`bash`, `yaml`, `json`).
  Use realistic file paths in the repo layout from earlier parts (`talos/`, `clusters/…`).
- Use Chirpy prompts for gotchas:
  ```
  > Short warning or tip.
  {: .prompt-warning }
  ```
  (`.prompt-tip`, `.prompt-info`, `.prompt-warning`, `.prompt-danger`)
- Write in a practical, opinionated, first-person voice ("I prefer…", "why I don't use X").
  Avoid marketing fluff. Use em-dashes sparingly.
- End with `## Final Thoughts`: what we have now (a bullet list of the stack), one
  "Next up: …" teaser for the next part, and a sign-off line like `Happy upgrading 🔄`.
- Length: about 250–450 lines of Markdown for a series part.
- Double-check that the commands and flags are real for the versions used (e.g. `talosctl`,
  `flux`, `kubectl`, Helm values). Prefer robust checks (`kubectl wait …`) over
  fragile `grep` pipelines.

### Future-dated posts and links

`future: false` is the default, and a daily workflow rebuilds at 07:15 UTC
(`.github/workflows/pages-deploy.yml`), so posts go live on their date.
**Never `post_url` a post whose date is still in the future**: the build fails. That's
why the previous part's "Next up:" can only get a link once the new post is live.
Offer that as a follow-up.

## 4. Cover image (when asked, or offer it)

The covers in the recent series use a dark navy background, circuit/particle texture,
neon cyan/teal glow, a two-tone headline, a center diagram, pills, and a tagline. Generate
one with the bundled script (1536×1024 PNG):

```bash
S=<scratchpad>/cover && mkdir -p $S
cat > $S/spec.json <<'JSON'
{"title":"Part 5: ","highlight":"Backups with Velero",
 "subtitle":"Talos Linux on Hetzner Bare Metal with Cilium",
 "nodes":[{"label":"Cluster","sub":"PVCs"},{"label":"Velero","sub":"schedule"},{"label":"S3","sub":"offsite"}],
 "pills":["restic","age","restore test"],
 "tagline":"snapshot · ship · restore"}
JSON
python3 .claude/skills/blog-post/scripts/cover.py $S/spec.json $S
node .claude/skills/blog-post/scripts/render.js $S/cover.html assets/img/<slug>.png
```

- `nodes` (2–4) draws glowing hexagons connected by arrows. For a richer, topic-specific
  center (a PR card, server, icons), pass raw SVG in `center_svg` instead. See the
  docstring in `cover.py` for the available filters, gradients, and classes.
- Glow on straight horizontal/vertical lines needs `#lineglow`, because `#glow` clips
  zero-height shapes. Gradients on such lines need `gradientUnits="userSpaceOnUse"`.
- **Always look at the PNG** (Read tool) before committing, and fix overlaps or clipped text.
- Playwright and Chromium are preinstalled. Don't run `playwright install`.

## 5. Verify the build

```bash
bundle install --quiet   # first time per session
bundle exec jekyll b --future -d /tmp/site-check 2>&1 | tail -5
```

Check that `/tmp/site-check/posts/<slug>/index.html` exists and that the cover path resolves.
`--future` is only for checking. Don't change `_config.yml`.

## 6. Commit and PR

- Commit style: `feat(blog): add <Series> Part N – <subtitle>` and
  `feat(blog): add cover image for <Series> Part N`.
- Push the session branch and open a PR (title like the commit, short body with an
  outline and the publish date). Mention to the user (in German) that the post goes live
  with the daily rebuild on its date at about 08:15.
