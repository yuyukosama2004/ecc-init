from fastapi import FastAPI
from langgraph.graph import StateGraph


app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "graph": StateGraph.__name__}
