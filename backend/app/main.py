from fastapi import FastAPI

app = FastAPI(title="Smart Market AI API")


@app.get("/health")
def health():
    return {"status": "ok"}
