from pathlib import Path
from typing import Literal

from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web
from pydantic import BaseModel, Field, ValidationError

from shelffee.config import settings
from shelffee.db import (
    Coffee,
    Recipe,
    Shelf,
    create_coffee,
    create_recipe,
    create_shelf,
    delete_coffee,
    delete_shelf,
    get_coffee_for_user,
    get_shelf_for_user,
    get_shelf_role,
    list_coffees,
    list_recipes,
    list_shelves,
    update_coffee,
    update_shelf,
    upsert_user,
)

STATIC_DIR = Path(__file__).parent / "static"


class ShelfIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class CoffeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    country: str = Field(min_length=1, max_length=64)
    flavor_notes: list[str] = Field(min_length=1)
    roast: Literal["filter", "espresso", "omni"]
    weight_grams: int = Field(gt=0)
    process: str = Field(min_length=1, max_length=64)
    region: str | None = Field(default=None, max_length=128)
    variety: str | None = Field(default=None, max_length=128)
    altitude_masl: int | None = Field(default=None, ge=0)
    farm: str | None = Field(default=None, max_length=128)
    sensory_scale: Literal[5, 10] | None = None
    acidity: int | None = Field(default=None, ge=0)
    sweetness: int | None = Field(default=None, ge=0)
    bitterness: int | None = Field(default=None, ge=0)
    body: int | None = Field(default=None, ge=0)


class RecipeIn(BaseModel):
    method: Literal[
        "espresso",
        "v60",
        "filter",
        "kalita",
        "chemex",
        "origami",
        "hario_switch",
        "clever",
        "aeropress",
        "french_press",
        "moka",
        "cezve",
        "siphon",
        "cold_brew",
        "batch_brew",
    ]
    dose_grams: float = Field(gt=0)
    grind: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)


def shelf_json(shelf: Shelf) -> dict:
    return {"id": shelf.id, "name": shelf.name, "created_at": shelf.created_at.isoformat()}


def coffee_json(coffee: Coffee) -> dict:
    return {
        "id": coffee.id,
        "shelf_id": coffee.shelf_id,
        "name": coffee.name,
        "country": coffee.country,
        "flavor_notes": coffee.flavor_notes,
        "roast": coffee.roast,
        "weight_grams": coffee.weight_grams,
        "process": coffee.process,
        "region": coffee.region,
        "variety": coffee.variety,
        "altitude_masl": coffee.altitude_masl,
        "farm": coffee.farm,
        "sensory_scale": coffee.sensory_scale,
        "acidity": coffee.acidity,
        "sweetness": coffee.sweetness,
        "bitterness": coffee.bitterness,
        "body": coffee.body,
        "created_at": coffee.created_at.isoformat(),
    }


def recipe_json(recipe: Recipe) -> dict:
    return {
        "id": recipe.id,
        "coffee_id": recipe.coffee_id,
        "method": recipe.method,
        "dose_grams": recipe.dose_grams,
        "grind": recipe.grind,
        "notes": recipe.notes,
        "created_at": recipe.created_at.isoformat(),
    }


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/api/"):
        return await handler(request)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("tma "):
        raise web.HTTPUnauthorized(text="Missing initData")
    try:
        init_data = safe_parse_webapp_init_data(settings.bot_token, auth[4:])
    except ValueError:
        raise web.HTTPUnauthorized(text="Invalid initData")
    tg_user = init_data.user
    request["user"] = await upsert_user(tg_user.id, tg_user.username, tg_user.first_name)
    return await handler(request)


async def parse_body(request: web.Request, model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        raise web.HTTPBadRequest(text=str(e))


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


async def me(request: web.Request) -> web.Response:
    user = request["user"]
    return web.json_response(
        {"id": user.id, "username": user.username, "first_name": user.first_name}
    )


async def shelves_list(request: web.Request) -> web.Response:
    shelves = await list_shelves(request["user"].id)
    return web.json_response([shelf_json(s) for s in shelves])


async def shelves_create(request: web.Request) -> web.Response:
    data = await parse_body(request, ShelfIn)
    shelf = await create_shelf(data.name, request["user"].id)
    return web.json_response(shelf_json(shelf), status=201)


async def require_shelf(request: web.Request) -> Shelf:
    shelf = await get_shelf_for_user(int(request.match_info["shelf_id"]), request["user"].id)
    if shelf is None:
        raise web.HTTPNotFound(text="Shelf not found")
    return shelf


async def shelf_update(request: web.Request) -> web.Response:
    shelf = await require_shelf(request)
    data = await parse_body(request, ShelfIn)
    shelf = await update_shelf(shelf.id, data.name)
    return web.json_response(shelf_json(shelf))


async def shelf_delete(request: web.Request) -> web.Response:
    shelf = await require_shelf(request)
    if await get_shelf_role(shelf.id, request["user"].id) != "owner":
        raise web.HTTPForbidden(text="Only the owner can delete a shelf")
    await delete_shelf(shelf.id)
    return web.Response(status=204)


async def shelf_share(request: web.Request) -> web.Response:
    shelf = await require_shelf(request)
    link = f"https://t.me/{request.app['bot_username']}?start=share_{shelf.share_token}"
    return web.json_response({"link": link})


async def coffees_list(request: web.Request) -> web.Response:
    shelf = await require_shelf(request)
    coffees = await list_coffees(shelf.id)
    role = await get_shelf_role(shelf.id, request["user"].id)
    return web.json_response(
        {"shelf": shelf_json(shelf), "role": role, "coffees": [coffee_json(c) for c in coffees]}
    )


async def coffees_create(request: web.Request) -> web.Response:
    shelf = await require_shelf(request)
    data = await parse_body(request, CoffeeIn)
    coffee = await create_coffee(shelf.id, **data.model_dump())
    return web.json_response(coffee_json(coffee), status=201)


async def require_coffee(request: web.Request) -> Coffee:
    coffee = await get_coffee_for_user(int(request.match_info["coffee_id"]), request["user"].id)
    if coffee is None:
        raise web.HTTPNotFound(text="Coffee not found")
    return coffee


async def coffee_get(request: web.Request) -> web.Response:
    coffee = await require_coffee(request)
    recipes = await list_recipes(coffee.id)
    return web.json_response({**coffee_json(coffee), "recipes": [recipe_json(r) for r in recipes]})


async def coffee_update(request: web.Request) -> web.Response:
    coffee = await require_coffee(request)
    data = await parse_body(request, CoffeeIn)
    coffee = await update_coffee(coffee.id, **data.model_dump())
    return web.json_response(coffee_json(coffee))


async def coffee_delete(request: web.Request) -> web.Response:
    coffee = await require_coffee(request)
    await delete_coffee(coffee.id)
    return web.Response(status=204)


async def recipes_create(request: web.Request) -> web.Response:
    coffee = await require_coffee(request)
    data = await parse_body(request, RecipeIn)
    recipe = await create_recipe(coffee.id, **data.model_dump())
    return web.json_response(recipe_json(recipe), status=201)


def setup_routes(app: web.Application) -> None:
    app.middlewares.append(auth_middleware)
    app.router.add_get("/", index)
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/shelves", shelves_list)
    app.router.add_post("/api/shelves", shelves_create)
    app.router.add_put("/api/shelves/{shelf_id:\\d+}", shelf_update)
    app.router.add_delete("/api/shelves/{shelf_id:\\d+}", shelf_delete)
    app.router.add_get("/api/shelves/{shelf_id:\\d+}/share", shelf_share)
    app.router.add_get("/api/shelves/{shelf_id:\\d+}/coffees", coffees_list)
    app.router.add_post("/api/shelves/{shelf_id:\\d+}/coffees", coffees_create)
    app.router.add_get("/api/coffees/{coffee_id:\\d+}", coffee_get)
    app.router.add_put("/api/coffees/{coffee_id:\\d+}", coffee_update)
    app.router.add_delete("/api/coffees/{coffee_id:\\d+}", coffee_delete)
    app.router.add_post("/api/coffees/{coffee_id:\\d+}/recipes", recipes_create)
    app.router.add_static("/static", STATIC_DIR)
