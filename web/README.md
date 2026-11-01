# Chennai Power Resilience Web App

The frontend is dependency-free vanilla JavaScript served by FastAPI from the same origin.

## Local

Install the package with the API extra, then run either entrypoint:

```sh
make install
make dashboard          # uvicorn drainage_rec.web_api:app --reload
```

Or, matching production exactly (no installed package required):

```sh
.venv/bin/python -m uvicorn app:app --port 8000
```

Open `http://localhost:8000`. No Node.js build or package install is needed.

## Vercel

`app.py` is the Vercel ASGI entrypoint and `vercel.json` holds the deployment
settings. See the "Deployment (Vercel)" section in the top-level README.

Charts use the vendored `plotly-basic.min.js` bundle (scatter and bar traces only).
If you add a trace type outside that bundle, vendor the matching larger bundle and
confirm it stays under Vercel's 4.5 MB function response limit.
