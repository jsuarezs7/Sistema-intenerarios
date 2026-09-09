from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from itinerary_shared.auth import Principal
from itinerary_shared.schemas import ItineraryInput
from pydantic import BaseModel, Field


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


def router(authenticate):
    routes = APIRouter()

    @routes.post("/auth/login", tags=["Authentication"])
    async def login(body: LoginBody, request: Request):
        token = request.app.state.service.login(body.username, body.password)
        return {"access_token": token, "token_type": "bearer", "expires_in": 3600}

    async def forward(request, principal, path, body=b""):
        status, content, media = await request.app.state.service.forward(
            request.method,
            path,
            principal.token,
            body,
            request.url.query,
        )
        headers = {"content-type": media}
        if status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return Response(content=content, status_code=status, headers=headers)

    @routes.get("/airports", tags=["Airports"])
    async def airports(request: Request, principal: Principal = Depends(authenticate)):
        return await forward(request, principal, "/airports")

    @routes.get("/airports/{airport_id}", tags=["Airports"])
    async def airport(
        request: Request, airport_id: int = Path(gt=0), principal: Principal = Depends(authenticate)
    ):
        return await forward(request, principal, f"/airports/{airport_id}")

    @routes.get("/itineraries", tags=["Itineraries"])
    async def itineraries(
        request: Request,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        principal: Principal = Depends(authenticate),
    ):
        return await forward(request, principal, "/itineraries")

    @routes.post("/itineraries", status_code=201, tags=["Itineraries"])
    async def create(
        body: ItineraryInput, request: Request, principal: Principal = Depends(authenticate)
    ):
        return await forward(request, principal, "/itineraries", body.model_dump_json().encode())

    @routes.get("/itineraries/{itinerary_id}", tags=["Itineraries"])
    async def detail(
        itinerary_id: UUID, request: Request, principal: Principal = Depends(authenticate)
    ):
        return await forward(request, principal, f"/itineraries/{itinerary_id}")

    @routes.put("/itineraries/{itinerary_id}", tags=["Itineraries"])
    async def update(
        itinerary_id: UUID,
        body: ItineraryInput,
        request: Request,
        principal: Principal = Depends(authenticate),
    ):
        return await forward(
            request, principal, f"/itineraries/{itinerary_id}", body.model_dump_json().encode()
        )

    @routes.delete("/itineraries/{itinerary_id}", status_code=204, tags=["Itineraries"])
    async def delete(
        itinerary_id: UUID, request: Request, principal: Principal = Depends(authenticate)
    ):
        return await forward(request, principal, f"/itineraries/{itinerary_id}")

    @routes.get("/reports", tags=["Reports"])
    async def report(request: Request, principal: Principal = Depends(authenticate)):
        return await forward(request, principal, "/reports")

    return routes
