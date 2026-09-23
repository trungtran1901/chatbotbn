import re
import json
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from app.rag.retrieval import retrieve_blocks, render_blocks, merge_blocks
from app.rag.direct_stream import stream_chat_completion, chat_completion
from app.db.postgres import (
    save_chat_message,
    load_chat_history,
    save_retrieval_cache,
    load_retrieval_cache,
)
from app.crawler.pipeline import run_crawl

app = FastAPI(title="Agno RAG Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("api")

NOT_FOUND_ANSWER = "Tôi không tìm thấy câu trả lời trong các tài nguyên hiện có."
LINK_PATTERN = re.compile(r"https?://[^\s\)\]\"',]+")
MAX_CONTEXT_BLOCKS = 12


class ChatRequest(BaseModel):
    chatinput: str
    sessionId: str


class CrawlRequest(BaseModel):
    pages: int = None


def build_user_message(chatinput: str, context: str) -> str:
    return f"NGUỒN DỮ LIỆU:\n{context}\n\nCÂU HỎI:\n{chatinput}"


def build_retrieval_query(session_id: str, current_question: str, lookback: int = 2) -> str:
    try:
        history = load_chat_history(session_id, limit=lookback * 2)
    except Exception:
        logger.exception("Loi doc lich su hoi thoai de mo rong truy van")
        return current_question

    recent_user_turns = [h["content"] for h in history if h["role"] == "user"]
    recent_user_turns = recent_user_turns[-lookback:]

    if not recent_user_turns:
        return current_question

    return " ".join(recent_user_turns + [current_question])


def get_context_for_turn(session_id: str, chatinput: str):
    retrieval_query = build_retrieval_query(session_id, chatinput)
    new_blocks = retrieve_blocks(retrieval_query)

    try:
        cached_blocks = load_retrieval_cache(session_id)
    except Exception:
        logger.exception("Loi doc retrieval cache")
        cached_blocks = []

    merged = merge_blocks(new_blocks, cached_blocks, max_total=MAX_CONTEXT_BLOCKS)

    if not merged:
        return None, []

    rendered = render_blocks(merged)
    return rendered, merged


def verify_grounding(answer: str, allowed_links: set) -> bool:
    cited_links = set(LINK_PATTERN.findall(answer))
    if not cited_links:
        return True
    invalid = cited_links - allowed_links
    if invalid:
        logger.warning("Phat hien link khong nam trong nguon du lieu duoc cap: %s", invalid)
        return False
    return True


@app.post("/chat/sync")
def chat_sync(req: ChatRequest):
    retrieval, merged_blocks = get_context_for_turn(req.sessionId, req.chatinput)

    if not retrieval:
        save_chat_message(req.sessionId, "user", req.chatinput)
        save_chat_message(req.sessionId, "assistant", NOT_FOUND_ANSWER)
        return JSONResponse({"answer": NOT_FOUND_ANSWER})

    message = build_user_message(req.chatinput, retrieval["context_text"])
    answer = chat_completion(req.sessionId, message)

    if not verify_grounding(answer, retrieval["allowed_links"]):
        answer = NOT_FOUND_ANSWER

    save_chat_message(req.sessionId, "user", req.chatinput)
    save_chat_message(req.sessionId, "assistant", answer)

    if answer != NOT_FOUND_ANSWER:
        try:
            save_retrieval_cache(req.sessionId, merged_blocks)
        except Exception:
            logger.exception("Loi luu retrieval cache")

    return JSONResponse({"answer": answer})


@app.post("/chat")
def chat(req: ChatRequest):
    result = chat_sync(req)
    answer = result.body.decode("utf-8")

    def stream():
        yield answer

    return StreamingResponse(stream(), media_type="application/json")


def sse_format(data: str, event: str = None) -> str:
    lines = []
    if event:
        lines.append(f"event: {event}")
    for line in data.split("\n"):
        lines.append(f"data: {line}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    retrieval, merged_blocks = get_context_for_turn(req.sessionId, req.chatinput)

    if not retrieval:
        def empty_stream():
            save_chat_message(req.sessionId, "user", req.chatinput)
            save_chat_message(req.sessionId, "assistant", NOT_FOUND_ANSWER)
            yield sse_format(json.dumps({"content": NOT_FOUND_ANSWER}, ensure_ascii=False))
            yield sse_format("[DONE]", event="done")
        return StreamingResponse(
            empty_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    message = build_user_message(req.chatinput, retrieval["context_text"])

    def token_stream():
        full_answer_holder = {"text": ""}
        try:
            for token in stream_chat_completion(req.sessionId, message, req.chatinput):
                full_answer_holder["text"] += token
                yield sse_format(json.dumps({"content": token}, ensure_ascii=False))
        except Exception:
            logger.exception("Loi trong luc stream cau tra loi")
            yield sse_format(json.dumps({"error": "Da xay ra loi khi sinh cau tra loi"}, ensure_ascii=False), event="error")
        finally:
            if full_answer_holder["text"]:
                try:
                    save_retrieval_cache(req.sessionId, merged_blocks)
                except Exception:
                    logger.exception("Loi luu retrieval cache")
            yield sse_format("[DONE]", event="done")

    return StreamingResponse(
        token_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/crawl")
def crawl(req: CrawlRequest):
    result = run_crawl(req.pages)
    return JSONResponse(result)


@app.get("/health")
def health():
    return {"status": "ok"}