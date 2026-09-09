from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from itinerary_shared.auth import Principal
from itinerary_shared.schemas import ItineraryInput, ItineraryView


def router(authenticate):
    routes = APIRouter()

    @routes.post("/itineraries", response_model=ItineraryView, status_code=201)
    async def create(
        body: ItineraryInput, request: Request, principal: Principal = Depends(authenticate)
    ):
        return await request.app.state.service.create(
            principal.user_id, principal.token, **body.model_dump()
        )

    @routes.get("/itineraries", response_model=list[ItineraryView])
    async def list_itineraries(
        request: Request,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        principal: Principal = Depends(authenticate),
    ):
        return await request.app.state.service.list(principal.user_id, offset, limit)

    @routes.get("/itineraries/{itinerary_id}", response_model=ItineraryView)
    async def get(
        itinerary_id: UUID, request: Request, principal: Principal = Depends(authenticate)
    ):
        return await request.app.state.service.get(itinerary_id, principal.user_id)

    @routes.put("/itineraries/{itinerary_id}", response_model=ItineraryView)
    async def update(
        itinerary_id: UUID,
        body: ItineraryInput,
        request: Request,
        principal: Principal = Depends(authenticate),
    ):
        return await request.app.state.service.update(
            itinerary_id, principal.user_id, principal.token, **body.model_dump()
        )

    @routes.delete("/itineraries/{itinerary_id}", status_code=204)
    async def delete(
        itinerary_id: UUID, request: Request, principal: Principal = Depends(authenticate)
    ):
        await request.app.state.service.delete(itinerary_id, principal.user_id)
        return Response(status_code=204)

    return routes
