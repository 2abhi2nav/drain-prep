# Chennai Power Resilience Web App

The frontend is dependency-free vanilla JavaScript served by FastAPI from the same origin.

Install the API extra in the project environment:

```sh
.venv/bin/pip install -e '.[api]'
.venv/bin/uvicorn drainage_rec.web_api:app --reload
```

Open `http://localhost:8000`. No Node.js build or package install is needed.
