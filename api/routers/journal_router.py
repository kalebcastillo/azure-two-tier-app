import logging
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends, Response
from repositories.postgres_repository import PostgresDB
from services.entry_service import EntryService
from models.entry import Entry, EntryCreate


router = APIRouter()

# TODO: Add authentication middleware
# TODO: Add request validation middleware
# TODO: Add rate limiting middleware
# TODO: Add API versioning
# TODO: Add response caching

async def get_entry_service() -> AsyncGenerator[EntryService, None]:
    async with PostgresDB() as db:
        yield EntryService(db)


@router.post("/entries", response_model=Entry, status_code=201)
async def create_entry(entry_data: EntryCreate, response: Response, entry_service: EntryService = Depends(get_entry_service)):
    try:
        created_entry = await entry_service.create_entry(entry_data.model_dump())
        response.headers["X-Detail"] = "Entry created successfully"
        return created_entry
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creating entry: {str(e)}")


@router.get("/entries")
async def get_all_entries(entry_service: EntryService = Depends(get_entry_service)):
    """Get all journal entries."""
    result = await entry_service.get_all_entries()
    if not result:
        raise HTTPException(status_code=404, detail="No entries found")
    return {"entries": result, "count": len(result)}


#Define response model as Entry to utilize "model_config" for datetime formatting.
@router.get("/entries/{entry_id}", response_model=Entry)
async def get_entry(entry_id: str, entry_service: EntryService = Depends(get_entry_service)):
    """Get a specific journal entry"""
    result = await entry_service.get_entry(entry_id)
    if not result:
        raise HTTPException(status_code=404, detail="Entry not found")
    return result
   

@router.patch("/entries/{entry_id}")
async def update_entry(entry_id: str, entry_update: dict, entry_service: EntryService = Depends(get_entry_service)):
    """Update a journal entry"""
    result = await entry_service.update_entry(entry_id, entry_update)
    if not result:
        raise HTTPException(status_code=404, detail="Entry not found")
    return result


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str, entry_service: EntryService = Depends(get_entry_service)):
    """Delete a specific journal entry"""
    await entry_service.delete_entry(entry_id)
    return {"detail": "Entry deleted"}


@router.delete("/entries")
async def delete_all_entries(entry_service: EntryService = Depends(get_entry_service)):
    """Delete all journal entries"""
    await entry_service.delete_all_entries()
    return {"detail": "All entries deleted"}