"""Tests for Google Custom Search configuration schema."""

import pytest
import voluptuous as vol

from custom_components.llm_intents.config_flow import get_google_search_schema
from custom_components.llm_intents.const import (
    CONF_BRAVE_NUM_RESULTS,
    CONF_GOOGLE_CSE_API_KEY,
    CONF_GOOGLE_CSE_CX,
)


def test_google_search_schema_valid():
    """Google CSE schema accepts valid data and returns defaults."""
    schema = get_google_search_schema(None)
    data = schema(
        {
            CONF_GOOGLE_CSE_API_KEY: "test-key",
            CONF_GOOGLE_CSE_CX: "cx-id",
            CONF_BRAVE_NUM_RESULTS: 3,
        }
    )

    assert data[CONF_GOOGLE_CSE_API_KEY] == "test-key"
    assert data[CONF_GOOGLE_CSE_CX] == "cx-id"
    assert data[CONF_BRAVE_NUM_RESULTS] == 3


def test_google_search_schema_invalid_num_results():
    """Google CSE schema enforces minimum number of results."""
    schema = get_google_search_schema(None)
    with pytest.raises(vol.Invalid):
        schema(
            {
                CONF_GOOGLE_CSE_API_KEY: "key",
                CONF_GOOGLE_CSE_CX: "cx",
                CONF_BRAVE_NUM_RESULTS: 0,
            }
        )
