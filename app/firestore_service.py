from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-e3b977f692c8"
COLLECTION_NAME = "recipes"

# Sensible seed catalog fallback
_IN_MEMORY_CATALOG = {
    "lemon-herb-chicken": {
        "id": "lemon-herb-chicken",
        "title": "Lemon Herb Grilled Chicken",
        "cuisine": "Mediterranean",
        "prep_time_mins": 15,
        "calories": 450,
        "dietary_tags": ["gluten-free", "nut-free", "peanut-free", "dairy-free"],
        "ingredients": ["chicken breast", "lemon juice", "olive oil", "thyme", "rosemary", "garlic"],
        "instructions": "Whisk lemon juice, olive oil, minced garlic, and herbs. Marinate chicken for 15 minutes. Grill on medium-high heat until cooked through."
    },
    "garlic-broccoli-pasta": {
        "id": "garlic-broccoli-pasta",
        "title": "Creamy Garlic Broccoli Pasta",
        "cuisine": "Italian",
        "prep_time_mins": 20,
        "calories": 520,
        "dietary_tags": ["vegetarian", "nut-free", "peanut-free"],
        "ingredients": ["penne pasta", "broccoli florets", "heavy cream", "parmesan cheese", "garlic", "butter"],
        "instructions": "Boil pasta and broccoli. Saute garlic in butter, add heavy cream and parmesan to make sauce. Toss pasta and broccoli in sauce."
    },
    "pan-seared-salmon": {
        "id": "pan-seared-salmon",
        "title": "Pan-Seared Salmon with Asparagus",
        "cuisine": "American",
        "prep_time_mins": 15,
        "calories": 480,
        "dietary_tags": ["keto", "gluten-free", "nut-free", "peanut-free", "dairy-free"],
        "ingredients": ["salmon filet", "asparagus spears", "olive oil", "lemon", "salt", "black pepper"],
        "instructions": "Season salmon filets with salt and pepper. Sear in olive oil skin-side down for 4 mins, flip for 3 mins. Saute asparagus in the same pan with lemon."
    }
}


def get_firestore_client():
    """Initializes Firestore client with hardcoded project ID."""
    return firestore.Client(project=PROJECT_ID)


def get_recipe_from_firestore(recipe_id: str) -> dict | None:
    """Reads a recipe document from Firestore by document ID."""
    try:
        db = get_firestore_client()
        doc = db.collection(COLLECTION_NAME).document(recipe_id).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"Firestore read exception ({e}), returning fallback catalog item if present.")
    return _IN_MEMORY_CATALOG.get(recipe_id)


def search_recipes_in_firestore(query: str = "", dietary_filter: str = "") -> list[dict]:
    """Queries Firestore recipes collection with filtering."""
    recipes = []
    try:
        db = get_firestore_client()
        docs = db.collection(COLLECTION_NAME).stream()
        for doc in docs:
            recipes.append(doc.to_dict())
    except Exception as e:
        print(f"Firestore query exception ({e}), using fallback catalog.")
        recipes = list(_IN_MEMORY_CATALOG.values())

    if not recipes:
        recipes = list(_IN_MEMORY_CATALOG.values())

    filtered = []
    for r in recipes:
        q_match = not query or (
            query.lower() in r.get("title", "").lower()
            or query.lower() in r.get("cuisine", "").lower()
            or any(query.lower() in ing.lower() for ing in r.get("ingredients", []))
        )
        d_match = not dietary_filter or (
            dietary_filter.lower() in [tag.lower() for tag in r.get("dietary_tags", [])]
        )
        if q_match and d_match:
            filtered.append(r)
    return filtered


def save_recipe_to_firestore(
    title: str,
    cuisine: str,
    prep_time_mins: int,
    calories: int,
    dietary_tags: list[str],
    ingredients: list[str],
    instructions: str
) -> str:
    """Writes a new recipe document to the Firestore 'recipes' collection."""
    recipe_id = title.lower().replace(" ", "-").replace("'", "").replace("&", "and")
    recipe_data = {
        "id": recipe_id,
        "title": title,
        "cuisine": cuisine,
        "prep_time_mins": prep_time_mins,
        "calories": calories,
        "dietary_tags": dietary_tags,
        "ingredients": ingredients,
        "instructions": instructions
    }
    _IN_MEMORY_CATALOG[recipe_id] = recipe_data
    try:
        db = get_firestore_client()
        db.collection(COLLECTION_NAME).document(recipe_id).set(recipe_data)
        return f"Successfully saved recipe '{title}' (ID: {recipe_id}) to Firestore collection '{COLLECTION_NAME}'."
    except Exception as e:
        print(f"Firestore write exception ({e}), saved to fallback catalog.")
        return f"Saved recipe '{title}' (ID: {recipe_id}) to catalog (Firestore fallback: {e})."
