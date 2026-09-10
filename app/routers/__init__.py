from fastapi import APIRouter, Query
from app.routers.health import router as health_router
from app.routers.items import router as items_router
from app.routers.sessions import router as sessions_router
from app.schemas.search import SearchResponse, SearchResultItem
from app.services.vector_service import VectorService

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(items_router, prefix="/items", tags=["Items"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["Sessions"])


@api_router.get("/search", response_model=SearchResponse, tags=["Search"])
async def global_semantic_search(
    q: str = Query(..., min_length=1, description="Semantic search query text"),
    limit: int = Query(5, ge=1, le=50, description="Max results to return")
):
    """Global semantic search across all past sessions using ChromaDB vector database."""
    raw_results = VectorService.search_sessions(query=q, limit=limit)
    items = [SearchResultItem(**item) for item in raw_results]
    return SearchResponse(query=q, count=len(items), results=items)


__all__ = ["api_router"]
