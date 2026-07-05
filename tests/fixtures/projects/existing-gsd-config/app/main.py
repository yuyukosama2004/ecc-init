from fastapi import FastAPI
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph


app = FastAPI()
echo = RunnableLambda(lambda value: value)


@app.get("/graph")
def graph() -> dict[str, str]:
    return {"graph": StateGraph.__name__, "echo": str(echo.invoke("ok"))}
