# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import os
import threading
import urllib.parse
import urllib.request
import uuid

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import storage
from google.genai import types

from app.a2ui_utils import a2ui_callback
from app.firestore_service import (
    get_recipe_from_firestore,
    save_recipe_to_firestore,
    search_recipes_in_firestore,
)
from app.maps_service import (
    find_nearby_places,
    geocode_address,
)

BUCKET_NAME = "personal-chef-agent-assets-e3b977f6"
PROJECT_ID = "qwiklabs-gcp-03-e3b977f692c8"
AGENT_ENGINE_RESOURCE_NAME = "projects/597656442262/locations/us-east1/reasoningEngines/2622689274989903872"


class PickleableAgentEngineSandboxCodeExecutor(AgentEngineSandboxCodeExecutor):
    """Subclass of AgentEngineSandboxCodeExecutor that handles threading.Lock serialization for cloudpickle deployment."""

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_agent_engine_creation_lock"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._agent_engine_creation_lock = threading.Lock()


# Build A2UI System Prompt using A2uiSchemaManager version 0.8
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Chef Gem, a personalized AI Personal Chef and Recipe assistant. "
        "You help users plan meals, calculate complex nutritional mathematical formulas using Python code execution in a secure sandbox, generate gourmet dish images and video clips using AI, discover local recipes from Firestore, fetch live global web recipes, scale ingredient quantities, geocode addresses, find nearby grocery stores or culinary spots, save new recipes, and find ingredient substitutions. "
        "CRITICAL ALLERGY & DIETARY REQUIREMENT: "
        "Whenever a user mentions ANY food allergy, intolerance, or dietary restriction (such as peanuts, tree nuts, shellfish, dairy, gluten, eggs, soy, sesame, etc.), "
        "you MUST explicitly recognize and save all user allergies into memory. "
        "Before suggesting recipes or substitutions, check all preloaded memories and ensure all recommended dishes strictly avoid ALL remembered user allergies without needing to be reminded."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


async def generate_memories_callback(callback_context: CallbackContext):
    """Write callback: after each turn, send the session to Memory Bank for extraction."""
    await callback_context.add_session_to_memory()
    return None


def generate_recipe_image(dish_name: str, tool_context: ToolContext) -> str:
    """Generate a photo of a plated dish or food item using gemini-3.1-flash-lite-image model in global region.

    Args:
        dish_name: Name or description of the recipe or dish (e.g. 'Lemon Herb Grilled Chicken', 'Zesty Lime Tacos').
        tool_context: ADK ToolContext provided automatically by the runner to save artifacts.

    Returns:
        The public Google Cloud Storage HTTPS URL of the generated image.
    """
    prompt = f"A professional high-resolution photo of a freshly cooked plated dish: {dish_name}. Bright natural studio lighting, gourmet presentation."

    # Generate image bytes using gemini-3.1-flash-lite-image in the global region
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
    )

    img_bytes = None
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                img_bytes = part.inline_data.data
                break

    if not img_bytes:
        return f"Error: Image generation failed for '{dish_name}'."

    safe_name = dish_name.lower().replace(" ", "_").replace("'", "")
    filename = f"{safe_name}_{uuid.uuid4().hex[:6]}.jpg"

    # 1. Save artifact to Playground's Artifacts panel via tool_context
    artifact_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
    tool_context.save_artifact(
        filename=filename,
        artifact=artifact_part,
        custom_metadata={"dish_name": dish_name, "model": "gemini-3.1-flash-lite-image"}
    )

    # 2. Upload directly to public GCS bucket (without writing local file)
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(img_bytes, content_type="image/jpeg")

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
    return public_url


def generate_recipe_video(dish_name: str, tool_context: ToolContext) -> str:
    """Generate a short video of a cooking dish or food item using Google's Omni model (gemini-omni-flash-preview) in global region.

    Args:
        dish_name: Name or description of the recipe or dish (e.g. 'Sizzling Garlic Butter Shrimp', 'Steaming Hot Ramen').
        tool_context: ADK ToolContext provided automatically by the runner to save artifacts.

    Returns:
        The public Google Cloud Storage HTTPS URL of the generated video.
    """
    prompt = f"A short video of a cooking dish: {dish_name}. Fresh ingredients, gourmet cooking action, bright studio lighting."

    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    interaction = client.interactions.create(
        model="gemini-omni-flash-preview",
        input=prompt,
    )

    if not interaction.output_video or not interaction.output_video.data:
        return f"Error: Video generation failed for '{dish_name}'."

    video_data = interaction.output_video.data
    if isinstance(video_data, str):
        video_bytes = base64.b64decode(video_data)
    else:
        video_bytes = video_data

    mime_type = interaction.output_video.mime_type or "video/mp4"
    safe_name = dish_name.lower().replace(" ", "_").replace("'", "")
    filename = f"{safe_name}_{uuid.uuid4().hex[:6]}.mp4"

    # 1. Save artifact to Playground's Artifacts panel via tool_context
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
    tool_context.save_artifact(
        filename=filename,
        artifact=artifact_part,
        custom_metadata={"dish_name": dish_name, "model": "gemini-omni-flash-preview"}
    )

    # 2. Upload directly to public GCS bucket (without writing local file)
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
    return public_url


def fetch_live_web_recipes(query: str = "chicken") -> str:
    """Fetch live web recipe suggestions and real-time culinary data from TheMealDB public global recipe database API.

    Args:
        query: Recipe keyword or main ingredient (e.g. 'chicken', 'pasta', 'beef', 'salmon', 'curry').

    Returns:
        Real recipe data from the web including ingredients, category, cuisine origin, thumbnail image, and step-by-step instructions.
    """
    api_key = os.getenv("MEALDB_API_KEY", "1")
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={encoded_query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AntigravityPersonalChef/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            meals = data.get("meals")
            if not meals:
                return f"No live web recipes found on TheMealDB matching query '{query}'."

            out = [f"Found {len(meals)} live web recipe(s) from TheMealDB for '{query}':\n"]
            for m in meals[:3]:
                title = m.get("strMeal")
                category = m.get("strCategory")
                area = m.get("strArea")
                instructions = (m.get("strInstructions") or "")[:200].replace("\r\n", " ") + "..."
                thumb = m.get("strMealThumb")

                ingredients = []
                for i in range(1, 21):
                    ing = m.get(f"strIngredient{i}")
                    meas = m.get(f"strMeasure{i}")
                    if ing and ing.strip():
                        ingredients.append(f"{meas.strip() if meas else ''} {ing.strip()}".strip())

                ing_str = ", ".join(ingredients[:6])
                out.append(
                    f"🍽️ **{title}** ({area} {category})\n"
                    f"   - Ingredients: {ing_str}\n"
                    f"   - Instructions Snippet: {instructions}\n"
                    f"   - Image URL: {thumb}\n"
                )
            return "\n".join(out)
    except Exception as e:
        return f"Error fetching live web recipes from TheMealDB API: {e}"


def search_recipes(query: str = "", dietary_restriction: str = "") -> str:
    """Search for recipes in the Firestore catalog based on cuisine, ingredients, or dietary preferences.

    Args:
        query: Search keywords or ingredients (e.g. 'chicken', 'pasta', 'salmon').
        dietary_restriction: Any dietary filter tag (e.g. 'gluten-free', 'nut-free', 'vegan', 'keto').

    Returns:
        Formatted summary of matching recipe documents retrieved from Firestore.
    """
    results = search_recipes_in_firestore(query=query, dietary_filter=dietary_restriction)
    if not results:
        return f"No recipes found in Firestore matching query='{query}' and filter='{dietary_restriction}'."

    out = [f"Found {len(results)} recipe(s) in Firestore:"]
    for r in results:
        tags = ", ".join(r.get("dietary_tags", []))
        out.append(
            f"- {r.get('title')} (ID: {r.get('id')}) | Cuisine: {r.get('cuisine')} | Prep: {r.get('prep_time_mins')}m | Calories: {r.get('calories')} kcal | Tags: [{tags}]"
        )
    return "\n".join(out)


def get_recipe_details(recipe_id: str) -> str:
    """Retrieve full recipe details (ingredients, prep time, instructions) from Firestore by document ID.

    Args:
        recipe_id: The document ID of the recipe (e.g. 'lemon-herb-chicken', 'garlic-broccoli-pasta').

    Returns:
        Detailed recipe information including full ingredient list and instructions.
    """
    recipe = get_recipe_from_firestore(recipe_id)
    if not recipe:
        return f"Recipe with ID '{recipe_id}' was not found in Firestore."

    tags = ", ".join(recipe.get("dietary_tags", []))
    ingredients = "\n  * ".join(recipe.get("ingredients", []))
    return (
        f"=== {recipe.get('title')} (ID: {recipe.get('id')}) ===\n"
        f"Cuisine: {recipe.get('cuisine')}\n"
        f"Prep Time: {recipe.get('prep_time_mins')} mins | Calories: {recipe.get('calories')} kcal\n"
        f"Dietary Tags: [{tags}]\n\n"
        f"Ingredients:\n  * {ingredients}\n\n"
        f"Instructions:\n{recipe.get('instructions')}"
    )


def calculate_scaled_nutrition(recipe_id: str, target_servings: int) -> str:
    """Calculate scaled ingredient quantities and nutritional macros for a target number of servings.

    Args:
        recipe_id: The document ID of the recipe in Firestore (e.g. 'lemon-herb-chicken', 'garlic-broccoli-pasta', 'pan-seared-salmon').
        target_servings: The number of people/servings to cook for (e.g. 4, 6, 8).

    Returns:
        Scaled ingredient quantities and estimated nutritional macro breakdown per serving and total.
    """
    recipe = get_recipe_from_firestore(recipe_id)
    if not recipe:
        return f"Recipe '{recipe_id}' was not found in database to calculate scaling."

    base_servings = 2
    scale_factor = max(1, target_servings) / base_servings
    base_calories = recipe.get("calories", 450)
    total_calories = int(base_calories * target_servings)

    # Macro estimations per serving
    protein_g = int(base_calories * 0.25 / 4)
    carbs_g = int(base_calories * 0.45 / 4)
    fat_g = int(base_calories * 0.30 / 9)

    scaled_ingredients = []
    for ing in recipe.get("ingredients", []):
        scaled_ingredients.append(f"{ing} (scaled x{scale_factor:.1f} for {target_servings} servings)")

    ingredients_text = "\n  * ".join(scaled_ingredients)
    return (
        f"=== Scaled Recipe: {recipe.get('title')} ({target_servings} Servings) ===\n"
        f"Scale Factor: {scale_factor:.1f}x (scaled from base {base_servings} servings)\n"
        f"Per-Serving Macros: {base_calories} kcal | Protein: {protein_g}g | Carbs: {carbs_g}g | Fat: {fat_g}g\n"
        f"Total Dish Energy: {total_calories} kcal across all {target_servings} servings\n\n"
        f"Scaled Ingredients ({target_servings} servings):\n  * {ingredients_text}"
    )


def save_new_recipe(
    title: str,
    cuisine: str,
    prep_time_mins: int,
    calories: int,
    dietary_tags: list[str],
    ingredients: list[str],
    instructions: str
) -> str:
    """Save a new recipe document to the Firestore 'recipes' collection.

    Args:
        title: Recipe title (e.g. 'Garlic Butter Shrimp').
        cuisine: Cuisine type (e.g. 'Italian', 'Mexican', 'Asian').
        prep_time_mins: Cooking/prep time in minutes.
        calories: Estimated calories per serving.
        dietary_tags: List of tags (e.g. ['gluten-free', 'nut-free', 'dairy-free']).
        ingredients: List of ingredient strings.
        instructions: Step-by-step cooking instructions.

    Returns:
        Confirmation message from Firestore.
    """
    return save_recipe_to_firestore(
        title=title,
        cuisine=cuisine,
        prep_time_mins=prep_time_mins,
        calories=calories,
        dietary_tags=dietary_tags,
        ingredients=ingredients,
        instructions=instructions
    )


def substitute_ingredient(ingredient: str) -> str:
    """Find culinary substitutes for a missing or restricted ingredient.

    Args:
        ingredient: Name of the ingredient to replace (e.g. 'peanut butter', 'heavy cream', 'butter').

    Returns:
        Recommended substitutes and adjustment ratio.
    """
    ing = ingredient.lower()
    if "peanut" in ing or "nut" in ing:
        return "Substitute for peanuts/nuts: Sunflower seed butter or tahini (1:1 ratio) for rich flavor without nut allergens."
    elif "butter" in ing:
        return "Substitute for butter: Olive oil or avocado oil (3/4 tbsp oil per 1 tbsp butter) or mashed avocado."
    elif "milk" in ing or "dairy" in ing or "cream" in ing:
        return "Substitute for dairy milk/cream: Oat milk or coconut cream (1:1 ratio)."
    return f"Substitute for {ingredient}: Greek yogurt or olive oil works well depending on whether it's baking or frying."


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=PickleableAgentEngineSandboxCodeExecutor(
        agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME,
    ),
    tools=[
        PreloadMemoryTool(),
        generate_recipe_image,
        generate_recipe_video,
        geocode_address,
        find_nearby_places,
        fetch_live_web_recipes,
        search_recipes,
        get_recipe_details,
        calculate_scaled_nutrition,
        save_new_recipe,
        substitute_ingredient,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
