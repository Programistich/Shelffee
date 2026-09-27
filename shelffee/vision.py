import base64
import io
from typing import Literal

from openai import AsyncOpenAI
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from shelffee.config import settings

PHOTO_MAX_SIDE = 1024


class CoffeeExtract(BaseModel):
    name: str | None = Field(description="Coffee name as printed on the bag, without the roaster name")
    roaster: str | None = Field(description="Roaster / brand name")
    country: str | None = Field(description="Country of origin")
    region: str | None = Field(description="Region within the country")
    farm: str | None = Field(description="Farm, washing station, cooperative or producer")
    variety: str | None = Field(description="Coffee variety / cultivar, e.g. Bourbon, SL28")
    altitude_masl: int | None = Field(description="Growing altitude in meters above sea level")
    process: str | None = Field(description="Processing method exactly as printed, e.g. Washed, Natural, Anaerobic")
    roast: Literal["filter", "espresso", "omni"] | None = Field(
        description="Roast profile: filter, espresso or omni"
    )
    weight_grams: int | None = Field(description="Package weight in grams")
    flavor_notes: list[str] = Field(description="Flavor descriptors printed on the label, one per item")
    sensory_scale: Literal[5, 10] | None = Field(
        description="Scale of the sensory scores if any are printed: 5 or 10"
    )
    acidity: int | None = Field(description="Acidity score on the sensory scale")
    sweetness: int | None = Field(description="Sweetness score on the sensory scale")
    bitterness: int | None = Field(description="Bitterness score on the sensory scale")
    body: int | None = Field(description="Body score on the sensory scale")


SYSTEM_PROMPT = (
    "You read photos of specialty coffee bags and labels. "
    "Extract only what is visible on the label; use null for anything that is not printed. "
    "Never guess values. Keep the original language and spelling of names and flavor notes. "
    "Infer roast from words like 'filter', 'espresso', 'omni', 'фільтр', 'еспресо'; "
    "otherwise leave it null."
)

_client: AsyncOpenAI | None = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    return _client


async def extract_coffee(image: bytes, content_type: str) -> CoffeeExtract:
    data_url = f"data:{content_type};base64,{base64.b64encode(image).decode()}"
    completion = await client().chat.completions.parse(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the coffee details from this label."},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                ],
            },
        ],
        response_format=CoffeeExtract,
    )
    message = completion.choices[0].message
    if message.refusal or message.parsed is None:
        raise ValueError(message.refusal or "Model returned no structured output")
    return message.parsed


def prepare_photo(image: bytes) -> bytes:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(image))).convert("RGB")
    img.thumbnail((PHOTO_MAX_SIDE, PHOTO_MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()
