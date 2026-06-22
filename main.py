from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from database import engine, Base
from config import settings
import models  # registers all models with Base
from routers import auth as auth_router
from routers import admin as admin_router
from routers import attendance as attendance_router
from routers import quiz as quiz_router
from routers import websocket as ws_router
from routers import ai as ai_router
from routers import student as student_router
from routers import teacher as teacher_router
from routers import parent as parent_router


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(attendance_router.router)
app.include_router(quiz_router.router)
app.include_router(ws_router.router)
app.include_router(ai_router.router)
app.include_router(student_router.router)
app.include_router(teacher_router.router)
app.include_router(parent_router.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/pages/login.html")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    messages = []
    for e in errors:
        loc = " → ".join(str(l) for l in e["loc"] if l != "body")
        messages.append(f"{loc}: {e['msg']}" if loc else e["msg"])
    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(messages)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if settings.DEBUG:
        import traceback
        return JSONResponse(status_code=500, content={"detail": str(exc), "trace": traceback.format_exc()})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
