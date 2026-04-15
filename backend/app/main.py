from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.calculate.router import router as calculate_router
from app.catalog.router import router as catalog_router
from app.projects.router import router as projects_router

app = FastAPI(title="MeuBess API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog_router)
app.include_router(projects_router)
app.include_router(calculate_router)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"ERRO GLOBAL: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor", "error": str(exc)},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
