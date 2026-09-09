from fastapi import APIRouter, Depends, Request
from itinerary_shared.auth import Principal

from app.domain.models import ItineraryReport


def router(authenticate):
    routes = APIRouter()

    @routes.get("/reports", response_model=ItineraryReport)
    async def generate(request: Request, principal: Principal = Depends(authenticate)):
        return await request.app.state.service.generate(principal.token)

    return routes
