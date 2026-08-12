import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as admin_users_router
from app.calculate.router import router as calculate_router
from app.catalog import scheduler as catalog_scheduler
from app.catalog.router import router as catalog_router
from app.feedback.router import router as feedback_router
from app.ploomes.router import router as ploomes_router
from app.projects.router import router as projects_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # O uvicorn configura os loggers DELE ('uvicorn', 'uvicorn.error'), não o
    # root. Um logger nosso sem handler no root cai no handler de último
    # recurso do Python, que só emite WARNING para cima — todo log.info() da
    # aplicação some. Foi o que escondeu o resultado do sync automático.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    tarefa = catalog_scheduler.iniciar(app)
    try:
        yield
    finally:
        if tarefa:
            tarefa.cancel()


app = FastAPI(title="MeuBess API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_users_router)
app.include_router(catalog_router)
app.include_router(projects_router)
app.include_router(calculate_router)
app.include_router(ploomes_router)
app.include_router(feedback_router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Traceback completo no log: sem ele, um NameError num ramo pouco exercitado
    # chega ao Railway como uma linha solta, sem arquivo nem linha.
    print(f"ERRO GLOBAL: {exc!r}")
    traceback.print_exception(type(exc), exc, exc.__traceback__)

    # A resposta de um exception handler NÃO passa pelo CORSMiddleware, então
    # sem estes cabeçalhos o navegador descarta o 500 e mostra "failed to fetch"
    # — o erro real fica invisível para quem está testando.
    origin = request.headers.get("origin")
    headers = {
        "Access-Control-Allow-Origin": origin or "*",
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    } if origin else {"Access-Control-Allow-Origin": "*"}

    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor", "error": str(exc)},
        headers=headers,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
