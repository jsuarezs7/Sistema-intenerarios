from fastapi import APIRouter, Depends, Path, Request

from app.domain.models import Airport


def router(authenticate):
    routes = APIRouter(dependencies=[Depends(authenticate)])

    @routes.get("/airports", response_model=list[Airport])
    async def list_airports(request: Request):
        return await request.app.state.service.list_airports()

    @routes.get("/airports/{airport_id}", response_model=Airport)
    async def get_airport(request: Request, airport_id: int = Path(gt=0)):
        return await request.app.state.service.get(airport_id)

    return routes
