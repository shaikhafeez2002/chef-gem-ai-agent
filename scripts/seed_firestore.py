import os
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-e3b977f692c8"

SEEDED_RECIPES = [
    {
        "id": "lemon-herb-chicken",
        "title": "Lemon Herb Grilled Chicken",
        "cuisine": "Mediterranean",
        "prep_time_mins": 15,
        "calories": 450,
        "dietary_tags": ["gluten-free", "nut-free", "peanut-free", "dairy-free"],
        "ingredients": ["chicken breast", "lemon juice", "olive oil", "thyme", "rosemary", "garlic"],
        "instructions": "Whisk lemon juice, olive oil, minced garlic, and herbs. Marinate chicken for 15 minutes. Grill on medium-high heat until cooked through."
    },
    {
        "id": "garlic-broccoli-pasta",
        "title": "Creamy Garlic Broccoli Pasta",
        "cuisine": "Italian",
        "prep_time_mins": 20,
        "calories": 520,
        "dietary_tags": ["vegetarian", "nut-free", "peanut-free"],
        "ingredients": ["penne pasta", "broccoli florets", "heavy cream", "parmesan cheese", "garlic", "butter"],
        "instructions": "Boil pasta and broccoli. Saute garlic in butter, add heavy cream and parmesan to make sauce. Toss pasta and broccoli in sauce."
    },
    {
        "id": "pan-seared-salmon",
        "title": "Pan-Seared Salmon with Asparagus",
        "cuisine": "American",
        "prep_time_mins": 15,
        "calories": 480,
        "dietary_tags": ["keto", "gluten-free", "nut-free", "peanut-free", "dairy-free"],
        "ingredients": ["salmon filet", "asparagus spears", "olive oil", "lemon", "salt", "black pepper"],
        "instructions": "Season salmon filets with salt and pepper. Sear in olive oil skin-side down for 4 mins, flip for 3 mins. Saute asparagus in the same pan with lemon."
    },
    {
        "id": "avocado-chickpea-salad",
        "title": "Zesty Avocado & Chickpea Salad",
        "cuisine": "Mexican",
        "prep_time_mins": 10,
        "calories": 380,
        "dietary_tags": ["vegan", "vegetarian", "gluten-free", "nut-free", "peanut-free", "dairy-free"],
        "ingredients": ["chickpeas", "ripe avocado", "cherry tomatoes", "lime juice", "cilantro", "cummin"],
        "instructions": "Rinse chickpeas and dice avocado and tomatoes. Toss together with lime juice, chopped cilantro, olive oil, and cumin."
    }
]


def seed_database():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("recipes")

    for recipe in SEEDED_RECIPES:
        doc_id = recipe["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(recipe)
        print(f"  ✓ Seeded recipe: {recipe['title']} (ID: {doc_id})")

    print("Firestore database seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
