# AI Safety Playbook for Small Businesses — website

A free, static website for **"AI Safety Playbook for Small Businesses"** by Emmanuel Diserbeau,
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Not legal advice.

Plain HTML, CSS, and vanilla JavaScript. No build step, no frameworks, no CDNs, no cookies,
no analytics or trackers. The risk check and policy generator run entirely in the visitor's
browser; nothing is sent anywhere or stored. Upload this folder as-is to any static host.

## What's in this folder

| Path | What it is |
|---|---|
| `index.html` | Landing page |
| `playbook.html` | Playbook introduction + contents |
| `why-ai-safety-matters.html` … `references.html` | One page per section (1–7), with prev/next navigation |
| `assessment.html` | Interactive 10-question AI Risk Self-Assessment (`?demo=1`, `?demo=low`, `?demo=high` pre-fill sample answers) |
| `policy.html` | AI Acceptable Use Policy generator (`?demo=1` pre-fills example values) |
| `404.html` | Not-found page (used automatically by GitHub Pages and Netlify) |
| `css/style.css` | All styles |
| `js/logic.js` | Pure scoring / template-filling logic (also unit-testable with Node) |
| `js/assessment.js`, `js/policy.js`, `js/site.js` | Page behaviour |
| `assets/favicon.svg`, `assets/og-image.png` | Favicon and social-sharing image |
| `downloads/` | The playbook as PDF and Word |
| `.nojekyll` | Tells GitHub Pages to serve files as-is |

## Updating the content

The HTML pages are generated from `playbook.md` (one folder up) by `site_build.py`:

```bash
pip install markdown
python3 site_build.py                              # regenerates the HTML in site/
SITE_URL=https://your-domain.example python3 site_build.py   # optional: absolute og:url / og:image / canonical
```

The generator also copies `AI_Safety_Playbook.pdf` and `.docx` into `site/downloads/`.
The CSS, JS, and assets are hand-written and are not overwritten.

> Tip: social networks need an absolute URL for `og:image`. Once you know your site's address,
> re-run the generator with `SITE_URL=...` so link previews show the image.

## Preview locally

```bash
cd site
python3 -m http.server 8000
# open http://localhost:8000
```

## Deploy free: GitHub Pages

1. Create a new **public** repository on GitHub (for example `ai-safety-playbook`).
2. Upload the **contents** of this `site/` folder to the repository root
   (on github.com: **Add file → Upload files**, drag everything in, including `.nojekyll`,
   then **Commit changes**). Or with git:
   ```bash
   cd site
   git init && git add . && git commit -m "AI Safety Playbook site"
   git branch -M main
   git remote add origin https://github.com/<you>/ai-safety-playbook.git
   git push -u origin main
   ```
3. In the repo go to **Settings → Pages**. Under **Build and deployment**, set
   **Source: Deploy from a branch**, **Branch: `main`**, folder **`/ (root)`**, and **Save**.
4. After a minute the site is live at `https://<you>.github.io/ai-safety-playbook/`.
   All links are relative, so it works in a sub-folder like this with no changes.
5. Optional: add a custom domain under **Settings → Pages → Custom domain**.

## Deploy free: Netlify (drag and drop)

1. Sign in at <https://app.netlify.com> (free plan).
2. Go to **Sites** → **Add new site → Deploy manually** (or open <https://app.netlify.com/drop>).
3. Drag the **`site` folder** (or the `ai-playbook-site.zip` file) onto the page.
4. Netlify gives you a URL like `https://random-name.netlify.app`. Rename it under
   **Site configuration → Change site name**, or add your own domain.
5. To update, drag the new folder onto the site's **Deploys** tab.

## Also works on

- **Cloudflare Pages**: Workers & Pages → Create → Pages → **Upload assets** → drop the `site` folder.
- Any web host that serves static files.

## License and attribution

Content: "AI Safety Playbook for Small Businesses" by Emmanuel Diserbeau, licensed under
CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). You may share and adapt it for any purpose,
including commercially, with attribution. If you change it, add: "Adapted by [YOUR NAME OR COMPANY]."

**Not legal advice.** This is general guidance, not legal, security, or compliance advice.
