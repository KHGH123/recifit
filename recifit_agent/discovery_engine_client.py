"""Direct (non-LLM) calls to Vertex AI Search (Discovery Engine).

Used instead of ADK's VertexAiSearchTool for anything where a downstream
tool call needs the exact document ID later (e.g. get_recipe(recipe_id)).
VertexAiSearchTool hands the model unstructured grounding text to compose an
answer from, and Gemini isn't guaranteed to transcribe an opaque ID from that
text correctly — in testing it fabricated sequential "1, 2, 3" ids instead.
Calling the API directly and returning structured JSON means the real id is
a plain field value the model copies, not something it has to read out of
prose.
"""
import os

from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1 as de

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("DISCOVERY_ENGINE_LOCATION", "global")


def _api_endpoint(location: str) -> str:
    if location == "global":
        return "global-discoveryengine.googleapis.com"
    return f"{location}-discoveryengine.googleapis.com"


_client_options = ClientOptions(api_endpoint=_api_endpoint(LOCATION))
_search_client = de.SearchServiceClient(client_options=_client_options)


def _serving_config_path(data_store_id: str) -> str:
    return _search_client.serving_config_path(
        project=PROJECT_ID,
        location=LOCATION,
        data_store=data_store_id,
        serving_config="default_search",
    )


def search_data_store(data_store_id: str, query: str, page_size: int = 5) -> list[dict]:
    """데이터스토어를 직접 검색해서 문서 ID와 구조화 데이터를 그대로 반환한다."""
    request = de.SearchRequest(
        serving_config=_serving_config_path(data_store_id),
        query=query,
        page_size=page_size,
    )
    response = _search_client.search(request=request)

    results = []
    for result in response.results:
        struct_data = dict(result.document.struct_data) if result.document.struct_data else {}
        results.append({"id": result.document.id, **struct_data})
    return results
