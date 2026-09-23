# 🍳 Chef Gem — AI Personal Chef Agent

An intelligent, interactive AI Personal Chef agent built with the **Google Agent Development Kit (ADK)**, deployed to **Vertex AI Agent Runtime**, and featuring **A2UI v0.8** declarative rich card rendering.

![Chef Gem Live Demo](./demo_recording.gif)

---

## 🌟 Overview & Implemented Capabilities

Chef Gem assists users with meal planning, allergy safety, recipe scaling, live web and database recipe discovery, AI image and video generation, and location-based ingredient sourcing.

### 🛠️ Core Capabilities & Google Cloud Services

- **Google Agent Development Kit (ADK) & Agent Runtime**:
  - Built with Python ADK (`google-adk`) and deployed on **Vertex AI Agent Runtime** using the Agent-to-Agent (A2A) protocol.

- **Long-Term Memory Bank**:
  - Uses `PreloadMemoryTool` and post-turn callbacks to extract and remember long-term user preferences and food allergies (e.g. peanut, dairy, gluten allergies) across turns.

- **Vertex AI Agent Engine Sandbox Code Executor**:
  - Securely executes Python code in a Vertex AI Agent Engine Sandbox to perform precise nutritional macro calculations and recipe scaling.

- **Google Cloud Firestore Database**:
  - Queries and stores recipe records in the project's Firestore database (`recipes` collection) via `search_recipes`, `get_recipe_details`, and `save_new_recipe`.

- **Google Cloud Storage (GCS)**:
  - Uploads generated media to a public Cloud Storage bucket (`personal-chef-agent-assets-e3b977f6`) for public URL serving.

- **AI Plated Dish Image Generation**:
  - Generates food photography using `gemini-3.1-flash-lite-image` in the `global` region, saving artifacts to the Playground panel and serving public GCS HTTPS image URLs.

- **AI Gourmet Video Generation**:
  - Generates cooking clips using Google's Omni model (`gemini-omni-flash-preview`) in the `global` region via `client.interactions.create`.

- **A2UI v0.8 Rich Card Interface**:
  - Formats structured agent responses using `A2uiSchemaManager` (version 0.8) and `BasicCatalog` to render responsive cards with images, ingredient lists, and cooking steps.

- **Google Maps Platform Integration**:
  - Provides geocoding (`geocode_address`) and local venue discovery (`find_nearby_places`) to locate nearby grocery stores and specialty culinary markets.

- **Live Web Recipe Search**:
  - Fetches real-time web recipes via `fetch_live_web_recipes` connecting to TheMealDB global API.

- **Nutritional Macro & Substitution Calculators**:
  - Features `calculate_scaled_nutrition` and `substitute_ingredient` to adapt recipes for dietary needs.

---

## 📁 Repository Structure

```
.
├── app/
│   ├── agent.py               # Root ADK agent configuration & tools
│   ├── a2ui_utils.py          # A2UI callback and surface formatter
│   ├── firestore_service.py   # Firestore database CRUD functions
│   └── maps_service.py        # Google Maps Geocoding & Places tools
├── frontend/
│   ├── main.py                # FastAPI proxy connecting to Agent Engine
│   ├── Dockerfile             # Container specification for Cloud Run
│   └── static/
│       └── index.html         # Rebranded dark glassmorphic web UI
├── agents-cli-manifest.yaml   # Manifest for agents-cli deployment
└── pyproject.toml             # Project dependencies and environment specs
```

---

## 🚀 Local Development & Setup Instructions

### Prerequisites
- Python 3.11+
- `uv` package manager installed
- Google Cloud SDK (`gcloud`) authenticated with project credentials

### 1. Install Dependencies
```bash
uv sync
```

### 2. Run Agent Locally in Playground
```bash
accli playground start
```

### 3. Run Web Frontend Locally
Navigate to the `frontend/` directory and launch the FastAPI proxy server:

```bash
cd frontend
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/<LOCATION>/reasoningEngines/<ENGINE_ID>"
export AGENT_DIRECTORY="app"
export PORT="8080"
uv run python main.py
```

---

## ☁️ Deployment Instructions

### Deploy Agent to Vertex AI Agent Runtime
```bash
agents-cli deploy --service-name personal-chef-agent-v9 --no-confirm-project
```

### Deploy Frontend Proxy to Cloud Run
```bash
cd frontend
gcloud run deploy personal-chef-frontend \
  --source . \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="<AGENT_ENGINE_RESOURCE_NAME>",AGENT_DIRECTORY="app"
```

Grant `roles/aiplatform.user` to the Cloud Run service account so it can reach the Agent Engine:
```bash
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:<CLOUD_RUN_SERVICE_ACCOUNT>" \
  --role="roles/aiplatform.user"
```
