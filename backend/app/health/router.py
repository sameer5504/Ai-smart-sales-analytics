from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def read_root():
    return {"message": "Backend is running"}


@router.get("/api/hello")
def hello():
    return {"message": "Hello from FastAPI backend!"}
