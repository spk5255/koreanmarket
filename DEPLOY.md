# Deploying the hosted demo (Streamlit Community Cloud)

A free, public link your friends can open in a browser — no install, no keys.
The hosted app runs on **synthetic data** and never calls live market or
Anthropic APIs, so a public URL **cannot cost you anything**.

## 1. Put this project on GitHub
```bash
cd korean-market-analyzer
git add -A && git commit -m "Korean Market Analyzer"      # already done for you
gh repo create korean-market-analyzer --public --source=. --push
# (or create a repo in the GitHub UI and: git remote add origin <url> && git push -u origin main)
```
> `.env` (your real keys), `.venv/`, `data/`, and `reports/` are git-ignored and will **not** be uploaded.

## 2. Deploy on Streamlit Community Cloud
1. Go to **https://share.streamlit.io** and sign in with GitHub.
2. **New app** → pick your `korean-market-analyzer` repo and branch.
3. Set **Main file path** to: `dashboard/app.py`
4. Click **Deploy**. First load seeds synthetic data and runs the model (~10–20s), then caches it.
5. Copy the `*.streamlit.app` URL and send it to friends.

## 3. (Optional) Password-protect the link
In the app's **Settings → Secrets** on Streamlit Cloud, add:
```toml
app_password = "choose-something"
```
The app will then prompt for it. (Leave it out for a fully open demo.)

## Notes
- Requirements come from `requirements.txt` (intentionally light — no pykrx/anthropic).
- To later show **real** market data instead of synthetic, that requires running
  live ingestion with your DART key on a host that allows it — a bigger step than
  the free demo. Ask and I'll set it up.
