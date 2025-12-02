import html
import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.json import JsonObjectType

from .cache import SQLiteCache
from .const import (
    CONF_BRAVE_NUM_RESULTS,
    CONF_GOOGLE_CSE_API_KEY,
    CONF_GOOGLE_CSE_CX,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GoogleSearchTool(llm.Tool):
    """Tool for searching the web via Google Custom Search Engine."""

    name = "search_web"
    description = (
        "Search the web to lookup information and answer user queries using Google "
        "Programmable Search."
    )
    response_instruction = """
    Review the results to provide the user with a clear and concise answer to their query.
    If the search results provided do not answer the user request, advise the user of this.
    You may offer to perform related searches for the user, and if confirmed, search new queries to continue assisting the user.
    Your response must be in plain-text, without the use of any formatting, and should be kept to 2-3 sentences.
    """

    parameters = vol.Schema(
        {
            vol.Required("query", description="The query to search for"): str,
        }
    )

    def wrap_response(self, response: dict) -> dict:
        response["instruction"] = self.response_instruction
        return response

    def _get_config(self, hass: HomeAssistant) -> dict[str, Any]:
        """Merge stored config with runtime options."""
        config_data = hass.data[DOMAIN].get("config", {})
        entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
        return {**config_data, **entry.options}

    async def cleanup_text(self, text: str) -> str:
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Call the tool."""
        config_data = self._get_config(hass)
        query = tool_input.tool_args["query"]
        _LOGGER.info("Google CSE web search requested for: %s", query)

        google_api_key = config_data.get(CONF_GOOGLE_CSE_API_KEY)
        google_cx = config_data.get(CONF_GOOGLE_CSE_CX)
        num_results = config_data.get(CONF_BRAVE_NUM_RESULTS, 2)
        num_results = max(1, min(int(num_results), 10))

        if not google_api_key or not google_cx:
            return {"error": "Google Custom Search not configured"}

        try:
            session = async_get_clientsession(hass)
            params = {
                "q": query,
                "num": num_results,
                "key": google_api_key,
                "cx": google_cx,
            }

            # Avoid storing API key in cache key
            cache_key = {k: v for k, v in params.items() if k != "key"}

            cache = SQLiteCache()
            cached_response = cache.get("google_cse_search", cache_key)
            if cached_response:
                return self.wrap_response(cached_response)

            async with session.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for item in data.get("items", []):
                        title = item.get("title", "")
                        snippet = item.get("snippet") or item.get("htmlSnippet", "")
                        cleaned_snippet = await self.cleanup_text(snippet)
                        results.append(
                            {"title": title, "description": cleaned_snippet}
                        )

                    response = {"results": results if results else "No results found"}

                    if results:
                        cache.set("google_cse_search", cache_key, response)
                        return self.wrap_response(response)

                    return response

                _LOGGER.error(
                    "Web search received a HTTP %s error from Google CSE", resp.status
                )
                return {"error": f"Search error: {resp.status}"}
        except Exception as e:
            _LOGGER.error("Web search error: %s", e)
            return {"error": f"Error searching web: {e!s}"}
