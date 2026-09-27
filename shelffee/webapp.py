import base64
import binascii
import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Literal

from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web
from pydantic import BaseModel, Field, ValidationError, field_validator

from shelffee.config import settings
from shelffee.db import (
    Coffee,
    Recipe,
    Shelf,
    create_coffee,
    create_recipe,
    create_shelf,
    delete_coffee,
    delete_recipe,
    delete_shelf,
    get_coffee_for_user,
    get_recipe_for_user,
    get_shelf_for_user,
    get_shelf_role,
    get_user,
    list_coffees,
    list_recipes,
    list_roasters,
    list_shelves_with_coffees,
    update_coffee,
    update_recipe,
    update_shelf,
    upsert_user,
)
from shelffee.vision import extract_coffee, prepare_photo

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PHOTO_BYTES = 2 * 1024 * 1024
LOGIN_MAX_AGE = 24 * 60 * 60
SESSION_MAX_AGE = 30 * 24 * 60 * 60
SESSION_COOKIE = "session"
SESSION_KEY = hashlib.sha256(f"shelffee-session:{settings.bot_token}".encode()).digest()
WIDGET_KEY = hashlib.sha256(settings.bot_token.encode()).digest()

STATIC_DIR = Path(__file__).parent / "static"
STATIC_VERSION = str(int(max(p.stat().st_mtime for p in STATIC_DIR.iterdir())))


class ShelfIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class CoffeeIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    roaster: str | None = Field(default=None, max_length=128)
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
    photo: bytes | None = None

    @field_validator("photo", mode="before")
    @classmethod
    def decode_photo(cls, v):
        if v is None or isinstance(v, bytes):
            return v
        try:
            raw = base64.b64decode(v, validate=True)
        except (binascii.Error, TypeError):
            raise ValueError("photo must be base64")
        if len(raw) > MAX_PHOTO_BYTES:
            raise ValueError("photo is too large")
        return raw

    def coffee_fields(self, *, partial_photo: bool = False) -> dict:
        fields = self.model_dump()
        if partial_photo and "photo" not in self.model_fields_set:
            fields.pop("photo")
        return fields


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
        "roaster": coffee.roaster,
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
        "has_photo": coffee.has_photo,
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


def verify_login_widget(query: dict[str, str]) -> dict[str, str]:
    data = {k: v for k, v in query.items() if k != "hash"}
    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    expected = hmac.new(WIDGET_KEY, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, query.get("hash", "")):
        raise web.HTTPUnauthorized(text="Invalid login data")
    if time.time() - int(data.get("auth_date", 0)) > LOGIN_MAX_AGE:
        raise web.HTTPUnauthorized(text="Login data is outdated")
    return data


def make_session(user_id: int) -> str:
    payload = f"{user_id}.{int(time.time())}"
    sig = hmac.new(SESSION_KEY, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def parse_session(token: str | None) -> int | None:
    if not token:
        return None
    try:
        user_id, issued, sig = token.split(".")
        payload = f"{user_id}.{issued}"
        expected = hmac.new(SESSION_KEY, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig) or time.time() - int(issued) > SESSION_MAX_AGE:
            return None
        return int(user_id)
    except ValueError:
        return None


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/api/"):
        return await handler(request)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("tma "):
        try:
            init_data = safe_parse_webapp_init_data(settings.bot_token, auth[4:])
        except ValueError:
            raise web.HTTPUnauthorized(text="Invalid initData")
        tg_user = init_data.user
        request["user"] = await upsert_user(tg_user.id, tg_user.username, tg_user.first_name)
        return await handler(request)
    user_id = parse_session(request.cookies.get(SESSION_COOKIE))
    user = await get_user(user_id) if user_id else None
    if user is None:
        raise web.HTTPUnauthorized(text="Not authenticated")
    request["user"] = user
    return await handler(request)


async def parse_body(request: web.Request, model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate(await request.json())
    except (ValidationError, ValueError) as e:
        raise web.HTTPBadRequest(text=str(e))


async def index(request: web.Request) -> web.Response:
    html = (
        (STATIC_DIR / "index.html")
        .read_text()
        .replace("{{v}}", STATIC_VERSION)
        .replace("{{bot}}", request.app["bot_username"])
    )
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache"})


async def auth_telegram(request: web.Request) -> web.Response:
    data = verify_login_widget(dict(request.query))
    user = await upsert_user(int(data["id"]), data.get("username"), data.get("first_name", ""))
    response = web.HTTPFound("/")
    response.set_cookie(
        SESSION_COOKIE,
        make_session(user.id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=settings.webapp_url.startswith("https://"),
        samesite="Lax",
    )
    return response


async def auth_logout(request: web.Request) -> web.Response:
    response = web.Response(status=204)
    response.del_cookie(SESSION_COOKIE)
    return response


async def me(request: web.Request) -> web.Response:
    user = request["user"]
    return web.json_response(
        {"id": user.id, "username": user.username, "first_name": user.first_name}
    )


async def shelves_list(request: web.Request) -> web.Response:
    shelves = await list_shelves_with_coffees(request["user"].id)
    return web.json_response(
        [
            {**shelf_json(shelf), "role": role, "coffees": [coffee_json(c) for c in shelf.coffees]}
            for shelf, role in shelves
        ]
    )


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


async def roasters_list(request: web.Request) -> web.Response:
    return web.json_response(await list_roasters())


async def coffees_create(request: web.Request) -> web.Response:
    shelf = await require_shelf(request)
    data = await parse_body(request, CoffeeIn)
    coffee = await create_coffee(shelf.id, **data.coffee_fields())
    return web.json_response(coffee_json(coffee), status=201)


async def coffees_recognize(request: web.Request) -> web.Response:
    reader = await request.multipart()
    field = await reader.next()
    if field is None or field.name != "image":
        raise web.HTTPBadRequest(text="Expected multipart field 'image'")
    content_type = field.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise web.HTTPBadRequest(text="File must be an image")
    image = await field.read(decode=False)
    if len(image) > MAX_IMAGE_BYTES:
        raise web.HTTPRequestEntityTooLarge(max_size=MAX_IMAGE_BYTES, actual_size=len(image))
    try:
        extracted = await extract_coffee(image, content_type)
        photo = prepare_photo(image)
    except Exception as e:
        logging.exception("Coffee recognition failed")
        raise web.HTTPBadGateway(text=f"Не вдалося розпізнати фото: {e}")
    return web.json_response(
        {**extracted.model_dump(), "photo": base64.b64encode(photo).decode()}
    )


async def require_coffee(request: web.Request) -> Coffee:
    coffee = await get_coffee_for_user(int(request.match_info["coffee_id"]), request["user"].id)
    if coffee is None:
        raise web.HTTPNotFound(text="Coffee not found")
    return coffee


async def coffee_get(request: web.Request) -> web.Response:
    coffee = await require_coffee(request)
    recipes = await list_recipes(coffee.id)
    return web.json_response({**coffee_json(coffee), "recipes": [recipe_json(r) for r in recipes]})


async def coffee_photo(request: web.Request) -> web.Response:
    coffee = await require_coffee(request)
    if coffee.photo is None:
        raise web.HTTPNotFound(text="No photo")
    return web.Response(body=coffee.photo, content_type="image/jpeg")


async def coffee_update(request: web.Request) -> web.Response:
    coffee = await require_coffee(request)
    data = await parse_body(request, CoffeeIn)
    coffee = await update_coffee(coffee.id, **data.coffee_fields(partial_photo=True))
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


async def require_recipe(request: web.Request) -> Recipe:
    recipe = await get_recipe_for_user(int(request.match_info["recipe_id"]), request["user"].id)
    if recipe is None:
        raise web.HTTPNotFound(text="Recipe not found")
    return recipe


async def recipe_update(request: web.Request) -> web.Response:
    recipe = await require_recipe(request)
    data = await parse_body(request, RecipeIn)
    recipe = await update_recipe(recipe.id, **data.model_dump())
    return web.json_response(recipe_json(recipe))


async def recipe_delete(request: web.Request) -> web.Response:
    recipe = await require_recipe(request)
    await delete_recipe(recipe.id)
    return web.Response(status=204)


def setup_routes(app: web.Application) -> None:
    app.middlewares.append(auth_middleware)
    app.router.add_get("/", index)
    app.router.add_get("/auth/telegram", auth_telegram)
    app.router.add_post("/auth/logout", auth_logout)
    app.router.add_get("/api/me", me)
    app.router.add_get("/api/shelves", shelves_list)
    app.router.add_post("/api/shelves", shelves_create)
    app.router.add_put("/api/shelves/{shelf_id:\\d+}", shelf_update)
    app.router.add_delete("/api/shelves/{shelf_id:\\d+}", shelf_delete)
    app.router.add_get("/api/shelves/{shelf_id:\\d+}/share", shelf_share)
    app.router.add_get("/api/shelves/{shelf_id:\\d+}/coffees", coffees_list)
    app.router.add_post("/api/shelves/{shelf_id:\\d+}/coffees", coffees_create)
    app.router.add_post("/api/coffees/recognize", coffees_recognize)
    app.router.add_get("/api/roasters", roasters_list)
    app.router.add_get("/api/coffees/{coffee_id:\\d+}", coffee_get)
    app.router.add_get("/api/coffees/{coffee_id:\\d+}/photo", coffee_photo)
    app.router.add_put("/api/coffees/{coffee_id:\\d+}", coffee_update)
    app.router.add_delete("/api/coffees/{coffee_id:\\d+}", coffee_delete)
    app.router.add_post("/api/coffees/{coffee_id:\\d+}/recipes", recipes_create)
    app.router.add_put("/api/recipes/{recipe_id:\\d+}", recipe_update)
    app.router.add_delete("/api/recipes/{recipe_id:\\d+}", recipe_delete)
    app.router.add_static("/static", STATIC_DIR)
