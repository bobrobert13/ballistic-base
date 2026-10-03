# Ballistic Base — BF6 Weapon Catalog

Single-page, self-contained Battlefield 6 weapon catalog (`bf6-armory.html`) generated from
sym.gg game-file dumps plus curated community data. All icons, weapon art, and map art are
base64-inlined at build time, so the shipped page has zero runtime dependencies.

Live: https://ballistic-base.vercel.app

## Build

Requires Python 3 (stdlib only).

```sh
python3 gen_final.py            # writes ./bf6-armory.html
python3 gen_final.py out/x.html # custom output path
```

Inputs read from the repo root: `bf6.json`, `rd_weapons.json`, `rd_attachments.json`,
`rd_attachment-tooltips.json`, `rd_ammo.json`, `att_icons.json`, `tiers.json`, `maps.json`,
`realworld.json`, `season.txt`, `template.html`, and the `icons/`, `webp/`, `mapwebp/` art
directories. The built page is committed, since Vercel serves it directly.

## Deploy (Vercel)

Static deployment, no build step.

| File | Role |
| --- | --- |
| `vercel.json` | `cleanUrls` plus rewrite `/` → `/bf6-armory`. Destination is extensionless because `cleanUrls` strips `.html` before routing. |
| `.vercelignore` | Allowlist: only `bf6-armory.html` and `vercel.json` are uploaded, so the CDN serves the catalog and nothing else. Build inputs stay in the repo. |

Project: `robert-webs-projects/ballistic-base` (`prj_HAJhKFrofJ8pCpqHILZ1myKqyQaY`),
production alias `ballistic-base.vercel.app`.

### Manual deploy

```sh
vercel deploy --prod
```

### Automatic deploys on push

The Vercel GitHub App can't currently see this repository, so Git integration is the one
step left. Either:

1. Grant the app access: GitHub → Settings → Applications → Vercel → Configure →
   Repository access → add `bobrobert13/ballistic-base` (or select all repositories), then
   `vercel git connect`; or
2. Import the repo in the Vercel dashboard (Add New → Project → `ballistic-base`), which
   links it in one step.

Once linked, pushes to `main` deploy to production and other branches get preview URLs.

## Layout

- `template.html` — HTML/CSS/JS shell with `__DATA__`-style placeholders.
- `gen_final.py` — data normalisation, tier/stat maths, placeholder substitution.
- `bf6.json` — sym.gg weapon dump (`info` holds version metadata).
- `rd_*.json` — attachments, ammo, tooltips, per-weapon attachment stats.
- `icons/`, `webp/`, `mapwebp/`, `imgs/`, `src/` — source art, inlined or used offline.
- `wi.html` — standalone page from a different project (bf6balancelog.com); intentionally
  excluded from the Vercel deployment by `.vercelignore`.
