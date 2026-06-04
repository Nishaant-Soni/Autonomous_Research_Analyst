from fastapi import FastAPI

app = FastAPI(title="Autonomous Research Analyst")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
