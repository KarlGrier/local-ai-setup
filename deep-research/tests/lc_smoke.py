"""Smoke test: langchain ChatOpenAI (as LDR builds it) against Strata, streaming + tool calls."""
import time, sys
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def web_search(query: str) -> str:
    """Search the web and return result snippets."""
    return "[1] Example result for " + query

for streaming in (False, True):
    llm = ChatOpenAI(model="strata-qwen3.8-flash-next-iq3s", api_key="x", base_url="http://127.0.0.1:8090/v1",
                     temperature=0.7, max_tokens=2000, streaming=streaming, request_timeout=600, max_retries=0,
                     reasoning_effort="low")
    t = time.time()
    r = llm.bind_tools([web_search]).invoke("Use the web_search tool to look up the population of Iceland. Call the tool.")
    print(f"streaming={streaming} {time.time()-t:.1f}s tool_calls={r.tool_calls} content={r.content[:120]!r}")
    print("  usage:", r.usage_metadata, "addl:", list(r.additional_kwargs.keys()), "meta:", {k: v for k, v in r.response_metadata.items() if k in ('finish_reason','model_name')})
