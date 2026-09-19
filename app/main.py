from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import init_db
from app.routes import auth, documents, questions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
)
logger = logging.getLogger('main')


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('Initializing database schema...')
    await init_db()
    logger.info('Database initialized successfully')
    yield
    logger.info('Application shutdown complete')


app = FastAPI(
    title='Pragati Bharati Document Intelligence API',
    description=(
        'Scalable Document Processing & Question Extraction Service accepting PDFs '
        'and images to produce structured, machine-readable questions and answer keys.'
    ),
    version='2.0.0',
    lifespan=lifespan,
    docs_url='/docs',
    redoc_url='/redoc',
    openapi_url='/openapi.json',
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f'Unhandled error on {request.method} {request.url.path}: {exc}')
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'detail': 'An internal server error occurred. Please try again later.'},
    )


# Include Routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(questions.router)


@app.get('/health', tags=['Health'])
def health_check():
    return {
        'status': 'ok',
        'service': 'Pragati Bharati Document Intelligence',
        'version': '2.0.0',
    }
