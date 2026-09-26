# Shelffee

Telegram bot with a Mini App. Python 3.12, aiogram 3, aiohttp, PostgreSQL, Docker.

## Idea

Shelffee is a coffee shelf: a place to keep track of the coffee you have, have tried, or want to try.

- A user can have multiple shelves.
- A shelf can be shared with other people, similar to shared lists in Apple Reminders: every participant sees the same shelf and can add and edit its contents.

## Data model

- `users` — Telegram users
- `shelves` — a shelf has a name and a unique `share_token`; ownership and sharing live in `shelf_members`
- `shelf_members` — `(shelf_id, user_id)` with `role` (`owner` / `member`); the creator gets `owner`, everyone the shelf is shared with gets `member`
- `coffees` — belongs to one shelf
  - required: `name`, `country`, `flavor_notes` (text array), `roast` (`filter` / `espresso` / `omni`), `weight_grams`, `process` (free text, wording varies between roasters)
  - optional: `region`, `variety`, `altitude_masl`, `farm`, and sensory scores `acidity` / `sweetness` / `bitterness` / `body` with `sensory_scale` (5 or 10) telling which scale the roaster uses
- `recipes` — belongs to one coffee; a record of how it was brewed
  - required: `method` (`espresso`, `v60`, `filter`, `kalita`, `chemex`, `origami`, `hario_switch`, `clever`, `aeropress`, `french_press`, `moka`, `cezve`, `siphon`, `cold_brew`, `batch_brew`), `dose_grams`
  - optional: `grind` (free text, e.g. grinder clicks), `notes`

## Sharing

A shelf is shared through a Telegram deep link:

```
https://t.me/shelffee_bot?start=share_<share_token>
```

Opening it sends `/start share_<share_token>` to the bot, which adds the user to `shelf_members` with role `member`. Repeated joins are a no-op; unknown tokens get an error message.

## Environments

Prod and dev are separate bots with separate stacks. A bot token cannot be shared: two pollers on one token get `409 Conflict`, and the menu button / Mini App URL are global per bot, so one bot cannot point at two deployments.

| | prod | dev |
|---|---|---|
| bot | `@shelffee_bot` | `@shelffee_dev_bot` |
| env file | `.env.prod` | `.env.dev` |
| compose project | `shelffee-prod` | `shelffee-dev` |
| host port | 8080 | 8081 |

The compose project name (`-p`) gives each environment its own network and its own `pgdata` volume, so dev cannot reach the prod database.

## Run

1. Create a bot via @BotFather and copy the token.
2. Expose the host port over HTTPS (e.g. `ngrok http 8081` for dev, or a reverse proxy in prod). Telegram requires HTTPS for Mini Apps.
3. `cp .env.example .env.dev` and fill `BOT_TOKEN`, `WEBAPP_URL`, `HOST_PORT`, `ENV_FILE`.
4. Start:

```
docker compose -p shelffee-dev  --env-file .env.dev  up --build -d
docker compose -p shelffee-prod --env-file .env.prod up --build -d
```

`--env-file` is used both for interpolation and, via `ENV_FILE`, to pick the file injected into the container. Omitting it falls back to `.env.dev`.

Migrations run automatically on container start. Send `/start` to the bot and press the button to open the Mini App.

## Layout

- `shelffee/main.py` — starts polling and the aiohttp server in one process
- `shelffee/handlers.py` — bot handlers
- `shelffee/webapp.py` — Mini App routes; `/api/me` validates `initData` via `aiogram.utils.web_app`
- `shelffee/static/` — Mini App frontend
- `shelffee/db.py` — SQLAlchemy models and session
- `migrations/` — Alembic

## New migration

```
docker compose -p shelffee-dev --env-file .env.dev run --rm bot alembic revision --autogenerate -m "describe change"
```
