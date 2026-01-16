#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post Informer for Home Assistant
AI-powered HUD display generator - gathers HA context, generates images, creates videos
"""

import sys
import os
import json
import base64
import requests
import subprocess
import re
from pathlib import Path
from datetime import datetime
from openai import OpenAI
from typing import Dict, List, Optional, Any, Union

# Jinja2 for template support
try:
    from jinja2 import Environment, Template
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

# Ensure UTF-8 output for proper character encoding
sys.stdout.reconfigure(encoding='utf-8')

# Version info
BUILD_VERSION = "1.0.6-pre-22"
BUILD_TIMESTAMP = "2026-01-16 00:00:00 UTC"

# ============================================================================
# CONFIGURATION FROM ENVIRONMENT
# ============================================================================

# API Configuration
API_KEY = os.environ.get("OPENAI_API_KEY", "")
PROMPT_MODEL = os.environ.get("PROMPT_MODEL", "gpt-5.2")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-1.5")

# Entity Monitoring
# Note: HA may pass this as a JSON-encoded list or a string
_entity_ids_raw = os.environ.get("ENTITY_IDS", "")
try:
    # Try to parse as JSON first (for list format from YAML)
    ENTITY_IDS = json.loads(_entity_ids_raw)
except (json.JSONDecodeError, TypeError):
    # If not JSON, use as-is (string format)
    ENTITY_IDS = _entity_ids_raw

# Prompt Customization
USE_DEFAULT_PROMPTS = os.environ.get("USE_DEFAULT_PROMPTS", "true").lower() == "true"
CUSTOM_SYSTEM_PROMPT = os.environ.get("CUSTOM_SYSTEM_PROMPT", "")
CUSTOM_USER_PROMPT = os.environ.get("CUSTOM_USER_PROMPT", "")

# Search Prompts (JSON array of search strings)
_search_prompts_raw = os.environ.get("SEARCH_PROMPTS", "[]")
try:
    SEARCH_PROMPTS = json.loads(_search_prompts_raw)
    if not isinstance(SEARCH_PROMPTS, list):
        SEARCH_PROMPTS = []
except (json.JSONDecodeError, TypeError):
    SEARCH_PROMPTS = []

# Image Configuration
IMAGE_QUALITY = os.environ.get("IMAGE_QUALITY", "high")
IMAGE_SIZE = os.environ.get("IMAGE_SIZE", "1536x1024")

# Resize Configuration
RESIZE_OUTPUT = os.environ.get("RESIZE_OUTPUT", "true").lower() == "true"
TARGET_RESOLUTION = os.environ.get("TARGET_RESOLUTION", "1080p")
SAVE_ORIGINAL = os.environ.get("SAVE_ORIGINAL", "true").lower() == "true"

# Video Configuration
ENABLE_VIDEO = os.environ.get("ENABLE_VIDEO", "true").lower() == "true"
VIDEO_DURATION = int(os.environ.get("VIDEO_DURATION", "1800"))
VIDEO_FRAMERATE = os.environ.get("VIDEO_FRAMERATE", "0.25")
USE_DEFAULT_FFMPEG = os.environ.get("USE_DEFAULT_FFMPEG", "true").lower() == "true"
CUSTOM_FFMPEG_ARGS = os.environ.get("CUSTOM_FFMPEG_ARGS", "")

# Output
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/media/post_informer")
FILENAME_PREFIX = os.environ.get("FILENAME_PREFIX", "post_informer")

# Supervisor API
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
SUPERVISOR_API = "http://supervisor/core/api"

# ============================================================================
# DEFAULT PROMPTS
# ============================================================================

def load_system_prompt() -> str:
    """Load system prompt from file, fallback to empty if not found"""
    script_dir = Path(__file__).parent
    system_prompt_path = script_dir / "system_prompt.txt"

    try:
        with open(system_prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        log(f"Warning: system_prompt.txt not found at {system_prompt_path}")
        return ""
    except Exception as e:
        log(f"Error loading system_prompt.txt: {e}")
        return ""

DEFAULT_USER_PROMPT_TEMPLATE = """
USER DATA:
Home Assistant Data:
{context}

USER REQUESTED SEARCHES:
{search_prompts}"""

# Resolution mapping (standard 16:9 aspect ratio)
RESOLUTION_MAP = {
    "4k": (3840, 2160),
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
}

# ============================================================================
# LOGGING
# ============================================================================

def log(msg: str, timing: Optional[float] = None):
    """Print to stdout for HA logs with optional timing"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if timing is not None:
        print(f"[post_informer] [{timestamp}] {msg} ({timing:.2f}s)", flush=True)
    else:
        print(f"[post_informer] [{timestamp}] {msg}", flush=True)

# ============================================================================
# HOME ASSISTANT INTEGRATION
# ============================================================================

def fire_event(event_type: str, data: dict):
    """Fire a Home Assistant event via Supervisor API"""
    if not SUPERVISOR_TOKEN:
        log("Warning: No SUPERVISOR_TOKEN, cannot fire event")
        return

    try:
        resp = requests.post(
            f"{SUPERVISOR_API}/events/{event_type}",
            headers={
                "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
                "Content-Type": "application/json"
            },
            json=data,
            timeout=10
        )
        log(f"Fired event {event_type}: HTTP {resp.status_code}")
    except Exception as e:
        log(f"Error firing event {event_type}: {e}")


def gather_ha_entities(entity_ids: List[str]) -> Dict[str, Any]:
    """Gather state information for specified HA entities"""
    if not SUPERVISOR_TOKEN:
        log("Warning: No SUPERVISOR_TOKEN, cannot gather entities")
        return {}

    if not entity_ids:
        log("No entity IDs configured, skipping entity gathering")
        return {}

    start_time = datetime.now()
    log(f"Gathering {len(entity_ids)} entity states...")
    log(f"Looking for: {entity_ids}")

    entities = {}

    try:
        # Get all states via Supervisor API
        resp = requests.get(
            f"{SUPERVISOR_API}/states",
            headers={
                "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        resp.raise_for_status()
        all_states = resp.json()

        log(f"API returned {len(all_states)} total states")

        # Filter to requested entities
        for state in all_states:
            entity_id = state.get("entity_id")
            if entity_id in entity_ids:
                entities[entity_id] = {
                    "state": state.get("state"),
                    "attributes": state.get("attributes", {}),
                    "last_changed": state.get("last_changed"),
                }

        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Gathered {len(entities)} entities", timing=elapsed)

        # Debug: show which entities were not found
        if len(entities) < len(entity_ids):
            missing = set(entity_ids) - set(entities.keys())
            log("=" * 60)
            log(f"⚠️  WARNING: Could not find {len(missing)} entities!")
            log(f"⚠️  Missing entities: {missing}")
            log("=" * 60)

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Error gathering entities: {e}", timing=elapsed)

    return entities


def discover_location_info(all_states: List[Dict[str, Any]]) -> Dict[str, str]:
    """Discover timezone and location from HA entities"""
    location_info = {
        "timezone": "America/Phoenix",  # Default fallback
        "location_name": None
    }

    # Look for zone.home which has timezone and location info
    for state in all_states:
        entity_id = state.get("entity_id")

        if entity_id == "zone.home":
            attrs = state.get("attributes", {})
            if "time_zone" in attrs:
                location_info["timezone"] = attrs["time_zone"]
            if "friendly_name" in attrs:
                location_info["location_name"] = attrs["friendly_name"]
            break

    log(f"Discovered location: timezone={location_info['timezone']}, location={location_info['location_name']}")
    return location_info


def build_jinja2_context(all_states: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build Jinja2 context with HA template functions"""
    # Create a dict mapping entity_id -> state object for quick lookup
    states_dict = {s.get("entity_id"): s for s in all_states}

    def states_func(entity_id: str) -> str:
        """Return state value for entity"""
        state_obj = states_dict.get(entity_id)
        if state_obj:
            return state_obj.get("state", "unknown")
        return "unknown"

    def state_attr_func(entity_id: str, attribute: str) -> Any:
        """Return specific attribute for entity"""
        state_obj = states_dict.get(entity_id)
        if state_obj:
            return state_obj.get("attributes", {}).get(attribute)
        return None

    def is_state_func(entity_id: str, state: str) -> bool:
        """Check if entity is in specific state"""
        return states_func(entity_id) == state

    # Create a States object that supports both function call and attribute access
    class States:
        """Mimics Home Assistant's states object - supports both states('entity_id') and states.domain.entity"""
        def __init__(self, states_dict):
            self._states_dict = states_dict

        def __call__(self, entity_id: str) -> str:
            """Allow states('entity_id') calls"""
            return states_func(entity_id)

        def __getattr__(self, domain: str):
            """Allow states.domain.entity access"""
            class DomainProxy:
                def __init__(self, domain, states_dict):
                    self.domain = domain
                    self._states_dict = states_dict

                def __getattr__(self, entity_name: str):
                    """Return a state object for domain.entity_name"""
                    entity_id = f"{self.domain}.{entity_name}"
                    state_obj = self._states_dict.get(entity_id)
                    if state_obj:
                        # Return an object that behaves like HA's state object
                        class StateObject:
                            def __init__(self, state_data):
                                self.entity_id = state_data.get("entity_id")
                                self.state = state_data.get("state", "unknown")
                                self.attributes = state_data.get("attributes", {})
                                self.last_changed = state_data.get("last_changed")

                        return StateObject(state_obj)
                    return None

            return DomainProxy(domain, self._states_dict)

    return {
        "states": States(states_dict),
        "state_attr": state_attr_func,
        "is_state": is_state_func,
    }


def process_entity_config(entity_config: Union[str, List[str]], all_states: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process entity_ids config - handles plain IDs, templates, and mixed formats

    Note: This parser uses depth tracking to separate templates from plain entity IDs.
    Edge case: Literal {{ or {% inside Jinja2 strings will confuse the depth counter.
    Example: {{ "Price is {{ value }}" }} will be flagged as incomplete.
    Workaround: Escape braces in strings: {{ "Price is \\{\\{ value \\}\\}" }}
    This edge case is rare enough that the warning message will catch it.
    """
    result = {}

    # Parse into list
    if isinstance(entity_config, list):
        entity_list = entity_config
    else:
        # Character-by-character parser for templates mixed with entity IDs
        # Parse the config string as-is (don't normalize whitespace first!)
        entity_list = []

        i = 0
        current_token = []
        template_depth = 0
        in_template = False

        while i < len(entity_config):
            char = entity_config[i]

            # Check for template start/end markers
            if i < len(entity_config) - 1:
                two_char = entity_config[i:i+2]

                if two_char in ('{{', '{%'):
                    # Starting a template
                    if not in_template:
                        # Save any accumulated non-template text as entity IDs
                        if current_token:
                            text = ''.join(current_token).strip()
                            if text:
                                # Split on spaces/commas
                                for item in re.split(r'[,\s]+', text):
                                    if item.strip():
                                        entity_list.append(item.strip())
                            current_token = []
                        in_template = True

                    template_depth += 1
                    current_token.append(two_char)
                    i += 2
                    continue

                elif two_char in ('}}', '%}'):
                    # Ending a template marker
                    template_depth -= 1
                    current_token.append(two_char)
                    i += 2

                    # If we've balanced all markers, this template is complete
                    if template_depth == 0 and in_template:
                        template = ''.join(current_token).strip()
                        if template:
                            entity_list.append(template)
                        current_token = []
                        in_template = False
                    continue

            # Regular character - just accumulate
            current_token.append(char)
            i += 1

        # Handle any remaining content
        if current_token:
            text = ''.join(current_token).strip()
            if in_template:
                # Incomplete template
                log(f"Warning: Incomplete template detected (unbalanced markers): {text[:80]}...")
                entity_list.append(text)
            elif text:
                # Plain entity IDs
                for item in re.split(r'[,\s]+', text):
                    if item.strip():
                        entity_list.append(item.strip())

        # Second pass: merge adjacent templates separated only by non-entity text
        # This handles cases where templates have labels/text mixed in
        merged_list = []
        i = 0
        while i < len(entity_list):
            item = entity_list[i]
            is_template = bool(re.search(r'\{[%{]', item))
            is_entity_id = re.match(r'^[a-z_]+\.[a-z0-9_]+$', item)

            if is_entity_id:
                # Plain entity ID - add it and move on
                merged_list.append(item)
                i += 1
            elif is_template:
                # Start collecting adjacent templates
                # First, look BACKWARD for any preceding non-entity text
                template_parts = []
                k = len(merged_list) - 1
                while k >= 0:
                    prev_item = merged_list[k]
                    prev_is_entity = re.match(r'^[a-z_]+\.[a-z0-9_]+$', prev_item)
                    prev_is_template = bool(re.search(r'\{[%{]', prev_item))

                    if prev_is_entity or prev_is_template:
                        # Hit an entity or template, stop looking back
                        break
                    else:
                        # Non-entity text, prepend it
                        template_parts.insert(0, merged_list.pop())
                        k -= 1

                # Add current template
                template_parts.append(item)
                j = i + 1

                # Look ahead for more templates, collecting any non-entity text between them
                while j < len(entity_list):
                    next_item = entity_list[j]
                    is_next_template = bool(re.search(r'\{[%{]', next_item))
                    is_entity_id = re.match(r'^[a-z_]+\.[a-z0-9_]+$', next_item)

                    if is_entity_id:
                        # Found a real entity ID, stop merging
                        break
                    elif is_next_template:
                        # Another template, add it
                        template_parts.append(next_item)
                        j += 1
                    else:
                        # Non-entity text (like "sun", "°", etc.), include it and keep looking
                        template_parts.append(next_item)
                        j += 1

                # Merge all parts into one template
                merged_template = ' '.join(template_parts)
                merged_list.append(merged_template)
                i = j
            else:
                # Non-entity, non-template text (will be collected by next template or entity)
                merged_list.append(item)
                i += 1

        entity_list = merged_list

    # Build state lookup dict
    states_dict = {s.get("entity_id"): s for s in all_states}

    # Separate plain entity IDs from templates
    plain_ids = []
    templates = []

    for item in entity_list:
        item = item.strip()
        if not item:
            continue

        # Check if it's a Jinja2 template (look for {% or {{)
        if re.search(r'\{[%{]', item):
            templates.append(item)
        else:
            plain_ids.append(item)

    # Process plain entity IDs
    for entity_id in plain_ids:
        state_obj = states_dict.get(entity_id)
        if state_obj:
            result[entity_id] = {
                "state": state_obj.get("state"),
                "attributes": state_obj.get("attributes", {}),
                "last_changed": state_obj.get("last_changed"),
            }

    # Process templates if Jinja2 is available
    if templates and JINJA2_AVAILABLE:
        log(f"Processing {len(templates)} Jinja2 templates...")
        jinja_context = build_jinja2_context(all_states)
        env = Environment()

        # Register HA-specific tests
        def is_state_test(entity_id, state):
            """Test if an entity is in a specific state"""
            return jinja_context['is_state'](entity_id, state)

        env.tests['is_state'] = is_state_test

        # Register HA-specific filters
        env.filters['state_attr'] = jinja_context['state_attr']

        # Enhanced int/float filters with default values (HA compatibility)
        def int_filter(value, default=0):
            """Convert to int with optional default"""
            try:
                return int(float(value))
            except (ValueError, TypeError):
                return default

        def float_filter(value, default=0.0):
            """Convert to float with optional default"""
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        env.filters['int'] = int_filter
        env.filters['float'] = float_filter

        for template_str in templates:
            try:
                template = env.from_string(template_str)
                rendered = template.render(jinja_context)
                result[template_str] = {"rendered_value": rendered}
                # Detailed rendering shown in ENTITY EXPOSURE section
            except Exception as e:
                log(f"❌ Error rendering template '{template_str[:50]}...': {e}")
                result[template_str] = {"error": str(e)}
    elif templates and not JINJA2_AVAILABLE:
        log("Warning: Jinja2 templates found but jinja2 library not available")
        for template_str in templates:
            result[template_str] = {"error": "jinja2 not installed"}

    return result


def log_entity_exposure(context: Dict[str, Any], show_missing: bool = True):
    """Log what entity data will be exposed - for transparency and debugging"""
    if not context:
        log("=" * 60)
        log("ENTITY EXPOSURE: No entities configured")
        log("=" * 60)
        return

    log("=" * 60)
    log("ENTITY EXPOSURE - Privacy & Debugging Info")
    log("=" * 60)
    log(f"Total entities/templates: {len(context)}")
    log("")

    for key, value in context.items():
        # Check if this is a template or plain entity
        if "rendered_value" in value:
            # Jinja2 template
            log(f"📝 Template: {key[:80]}{'...' if len(key) > 80 else ''}")
            log(f"   → Rendered: {value['rendered_value']}")
        elif "error" in value:
            # Template with error
            log(f"❌ Template (ERROR): {key[:80]}{'...' if len(key) > 80 else ''}")
            log(f"   → Error: {value['error']}")
        else:
            # Plain entity
            log(f"🏠 Entity: {key}")
            log(f"   State: {value.get('state', 'unknown')}")

            # Log key attributes (skip internal/verbose ones)
            attrs = value.get('attributes', {})
            if attrs:
                # Filter to most relevant attributes
                skip_attrs = {'entity_picture', 'icon', 'supported_features',
                             'device_class', 'state_class', 'last_reset'}
                relevant_attrs = {k: v for k, v in attrs.items()
                                 if k not in skip_attrs and not k.startswith('_')}

                if relevant_attrs:
                    log(f"   Attributes:")
                    for attr_key, attr_val in list(relevant_attrs.items())[:5]:  # Limit to 5
                        # Truncate long values
                        val_str = str(attr_val)
                        if len(val_str) > 60:
                            val_str = val_str[:60] + "..."
                        log(f"     • {attr_key}: {val_str}")

                    if len(relevant_attrs) > 5:
                        log(f"     ... and {len(relevant_attrs) - 5} more attributes")

    log("=" * 60)


def run_startup_entity_scan():
    """Run entity scan at startup for transparency and debugging"""
    log("=" * 60)
    log("STARTUP ENTITY SCAN")
    log("=" * 60)

    if not SUPERVISOR_TOKEN:
        log("⚠️  No SUPERVISOR_TOKEN - cannot scan entities")
        log("=" * 60)
        return

    if not ENTITY_IDS:
        log("⚠️  No entity_ids configured")
        log("=" * 60)
        return

    try:
        # Fetch all states
        log("Fetching all Home Assistant states...")
        resp = requests.get(
            f"{SUPERVISOR_API}/states",
            headers={
                "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        resp.raise_for_status()
        all_states = resp.json()
        log(f"Retrieved {len(all_states)} total states from HA")

        # Process entity config
        log(f"Processing entity configuration...")
        context = process_entity_config(ENTITY_IDS, all_states)

        # Show what will be exposed (includes any missing entity warnings)
        log_entity_exposure(context)

    except Exception as e:
        log(f"❌ Error during startup entity scan: {e}")
        log("=" * 60)


# ============================================================================
# PIPELINE STEPS
# ============================================================================

def generate_prompt_from_context(context: Dict[str, Any], location_info: Dict[str, str]) -> tuple[Optional[str], Dict[str, Any]]:
    """Call OpenAI to generate an image prompt based on HA context

    Returns:
        tuple: (prompt_text, metadata_dict) where metadata includes tokens and search_count
    """
    start_time = datetime.now()

    # Format search prompts for display
    search_prompts_formatted = "\n".join(SEARCH_PROMPTS) if SEARCH_PROMPTS else "(none)"

    # Transform context to extract rendered values from templates
    # This ensures we send clean rendered text to the AI, not the template strings
    transformed_context = {}
    template_counter = 0

    for key, value in (context or {}).items():
        if isinstance(value, dict) and "rendered_value" in value:
            # This is a rendered template - use clean key and extract rendered value
            template_counter += 1
            clean_key = f"rendered_template_{template_counter}" if template_counter > 1 else "rendered_template"
            transformed_context[clean_key] = value["rendered_value"]
        elif isinstance(value, dict) and "error" in value:
            # Template rendering error - include for debugging
            template_counter += 1
            clean_key = f"template_{template_counter}_error"
            transformed_context[clean_key] = f"[Error: {value['error']}]"
        else:
            # Plain entity - keep as-is
            transformed_context[key] = value

    # Load default prompts (always, so they can be referenced in custom prompts)
    default_system_prompt = load_system_prompt()
    default_user_prompt = DEFAULT_USER_PROMPT_TEMPLATE.format(
        context=json.dumps(transformed_context, indent=2),
        search_prompts=search_prompts_formatted
    )

    # Build available variables for custom prompt substitution
    prompt_variables = {
        # Core data
        "context": json.dumps(transformed_context, indent=2),
        "search_prompts": search_prompts_formatted,

        # Default prompts (for extending/modifying)
        "default_system_prompt": default_system_prompt,
        "default_user_prompt": default_user_prompt,

        # Location info
        "location_name": location_info.get("location_name", "Unknown"),
        "timezone": location_info.get("timezone", "UTC"),

        # Config info
        "prompt_model": PROMPT_MODEL,
        "image_model": IMAGE_MODEL,
    }

    # Choose prompts
    if USE_DEFAULT_PROMPTS:
        system_prompt = default_system_prompt
        user_prompt = default_user_prompt
    else:
        system_prompt = CUSTOM_SYSTEM_PROMPT.format(**prompt_variables) if CUSTOM_SYSTEM_PROMPT else default_system_prompt
        user_prompt = CUSTOM_USER_PROMPT.format(**prompt_variables) if CUSTOM_USER_PROMPT else default_user_prompt

    log(f"Generating art prompt with {PROMPT_MODEL}...")
    log(f"Context size: {len(json.dumps(transformed_context))} chars")
    log(f"Search prompts in request: {len(SEARCH_PROMPTS)}")
    if SEARCH_PROMPTS:
        for i, sp in enumerate(SEARCH_PROMPTS, 1):
            log(f"  [{i}] {sp}")
    if location_info.get("location_name"):
        log(f"Location: {location_info['location_name']} ({location_info['timezone']})")

    try:
        client = OpenAI(api_key=API_KEY)

        # Try Responses API first for web_search support
        try:
            log("Attempting Responses API with web_search...")
            response = client.responses.create(
                model=PROMPT_MODEL,
                input=[
                    {
                        "role": "developer",
                        "content": [
                            {
                                "type": "input_text",
                                "text": system_prompt
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": user_prompt
                            }
                        ]
                    }
                ],
                text={
                    "format": {"type": "text"},
                    "verbosity": "medium"
                },
                reasoning={
                    "effort": "medium",
                    "summary": "auto"
                },
                tools=[
                    {
                        "type": "web_search",
                        "user_location": {
                            "type": "approximate"
                        },
                        "search_context_size": "medium"
                    }
                ],
                store=True
            )

            # Extract the text from the response
            # The response is in the output field
            prompt = None
            tokens_used = {"input": 0, "output": 0, "total": 0}

            # Parse response output
            if hasattr(response, 'output') and response.output is not None:
                for item in response.output:
                    if hasattr(item, 'content') and item.content:
                        for content_item in item.content:
                            if hasattr(content_item, 'type') and content_item.type == "output_text":
                                if hasattr(content_item, 'text'):
                                    prompt = content_item.text.strip()
                                    break
                    if prompt:
                        break

            # Capture token usage
            if hasattr(response, 'usage'):
                usage = response.usage
                if hasattr(usage, 'input_tokens'):
                    tokens_used["input"] = usage.input_tokens
                if hasattr(usage, 'output_tokens'):
                    tokens_used["output"] = usage.output_tokens
                if hasattr(usage, 'total_tokens'):
                    tokens_used["total"] = usage.total_tokens
                log(f"Tokens - Input: {tokens_used['input']}, Output: {tokens_used['output']}, Total: {tokens_used['total']}")

            # Log web search activity
            search_count = 0
            if hasattr(response, 'output') and response.output is not None:
                for item in response.output:
                    if hasattr(item, 'content') and item.content:
                        for content_item in item.content:
                            if hasattr(content_item, 'type') and content_item.type == "tool_use":
                                if hasattr(content_item, 'name') and content_item.name == "web_search":
                                    search_count += 1
                                    # Extract search query if available
                                    if hasattr(content_item, 'input') and isinstance(content_item.input, dict):
                                        query = content_item.input.get('query', 'unknown')
                                        log(f"🔍 Web Search #{search_count}: {query}")
                            elif hasattr(content_item, 'type') and content_item.type == "tool_result":
                                # Log search results summary
                                if hasattr(content_item, 'content'):
                                    result_text = str(content_item.content)
                                    result_preview = result_text[:150] + "..." if len(result_text) > 150 else result_text
                                    log(f"   ↳ Result: {result_preview}")

            if search_count > 0:
                log(f"✓ Total web searches performed: {search_count}")
            else:
                log("ℹ️  No web searches were triggered by the model")

            if not prompt:
                raise Exception("No output_text found in Responses API response")

        except Exception as responses_error:
            log(f"Responses API failed: {responses_error}")
            log("Falling back to Chat Completions API without web_search...")

            # Fall back to Chat Completions API
            response = client.chat.completions.create(
                model=PROMPT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=4096,
                temperature=1.0
            )

            prompt = response.choices[0].message.content.strip()
            search_count = 0  # No searches in fallback mode

        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Generated prompt ({len(prompt)} chars)", timing=elapsed)
        log("=" * 60)
        log("FULL PROMPT FOR IMAGE GENERATION:")
        log("=" * 60)
        log(prompt)
        log("=" * 60)

        metadata = {
            "tokens": tokens_used,
            "search_count": search_count,
            "generation_time": elapsed
        }
        return prompt, metadata

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Error generating prompt: {e}", timing=elapsed)
        return None, {}


def generate_image(prompt: str, filename: str) -> Optional[Dict[str, Any]]:
    """Generate image via OpenAI API and save to output directory"""
    start_time = datetime.now()

    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    filepath = output_path / filename

    log(f"Rendering image with {IMAGE_MODEL}...")
    log(f"Quality: {IMAGE_QUALITY}, Size: {IMAGE_SIZE}")

    try:
        client = OpenAI(api_key=API_KEY)

        generate_params = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "n": 1,
            "size": IMAGE_SIZE,
            "quality": IMAGE_QUALITY,
        }

        # output_format only supported for gpt-image models
        if "gpt-image" in IMAGE_MODEL:
            generate_params["output_format"] = "png"
        else:
            generate_params["response_format"] = "b64_json"

        response = client.images.generate(**generate_params)

        # Decode and save image
        image_data = base64.b64decode(response.data[0].b64_json)
        filepath.write_bytes(image_data)

        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Image rendered: {filepath}", timing=elapsed)

        return {
            "success": True,
            "filepath": str(filepath),
            "filename": filename,
            "size": IMAGE_SIZE,
            "render_time": elapsed
        }

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Error rendering image: {e}", timing=elapsed)
        return {
            "success": False,
            "error": str(e),
            "render_time": elapsed
        }


def resize_image(input_path: str, output_path: str, resolution: str) -> Optional[Dict[str, Any]]:
    """Resize image using ffmpeg"""
    start_time = datetime.now()

    # Determine target dimensions
    if resolution in RESOLUTION_MAP:
        width, height = RESOLUTION_MAP[resolution]
    else:
        # Custom format: "WIDTHxHEIGHT"
        try:
            width, height = map(int, resolution.split('x'))
        except:
            log(f"Invalid resolution format: {resolution}")
            return {"success": False, "error": f"Invalid resolution: {resolution}"}

    log(f"Resizing to {width}x{height}...")

    try:
        cmd = [
            "ffmpeg",
            "-y",                      # Overwrite output
            "-i", input_path,          # Input file
            "-vf", f"scale={width}:{height}",  # Scale filter
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            raise Exception(f"ffmpeg failed: {result.stderr}")

        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Image resized: {output_path}", timing=elapsed)

        return {
            "success": True,
            "filepath": output_path,
            "resolution": f"{width}x{height}",
            "resize_time": elapsed
        }

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Error resizing image: {e}", timing=elapsed)
        return {
            "success": False,
            "error": str(e),
            "resize_time": elapsed
        }


def create_video(input_path: str, output_path: str) -> Optional[Dict[str, Any]]:
    """Create video from image using ffmpeg"""
    start_time = datetime.now()

    log(f"Creating video ({VIDEO_DURATION}s @ {VIDEO_FRAMERATE} fps)...")

    try:
        if USE_DEFAULT_FFMPEG:
            cmd = [
                "ffmpeg",
                "-y",                           # Overwrite output
                "-framerate", VIDEO_FRAMERATE,  # Input framerate (BEFORE -i!)
                "-loop", "1",                   # Loop the input image
                "-i", input_path,               # Input file
                "-t", str(VIDEO_DURATION),      # Duration in seconds
                "-c:v", "libx264",              # H.264 codec
                "-preset", "ultrafast",         # Speed over size
                "-tune", "stillimage",          # Optimize for static image
                "-pix_fmt", "yuv420p",          # Compatibility
                "-movflags", "+faststart",      # Enable streaming
                output_path
            ]
        else:
            # Parse custom ffmpeg args
            cmd = ["ffmpeg"] + CUSTOM_FFMPEG_ARGS.split() + [output_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for video encoding
        )

        if result.returncode != 0:
            raise Exception(f"ffmpeg failed: {result.stderr}")

        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Video created: {output_path}", timing=elapsed)

        return {
            "success": True,
            "filepath": output_path,
            "duration": VIDEO_DURATION,
            "framerate": VIDEO_FRAMERATE,
            "encode_time": elapsed
        }

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Error creating video: {e}", timing=elapsed)
        return {
            "success": False,
            "error": str(e),
            "encode_time": elapsed
        }


def embed_metadata(image_path: str, prompt: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Embed prompt and metadata into PNG using ImageMagick"""
    try:
        # Build command with comprehensive metadata
        cmd = [
            "convert",
            image_path,
            "-set", "Description", prompt,  # Full prompt in Description
            "-set", "comment", prompt,      # Also in comment for compatibility
        ]

        # Add additional metadata if provided
        if metadata:
            # Add model info as Software
            if "model" in metadata:
                cmd.extend(["-set", "Software", f"OpenAI {metadata['model']}"])

            # Add prompt model if available
            if "prompt_model" in metadata:
                cmd.extend(["-set", "comment:prompt_model", metadata['prompt_model']])

            # Add image model if available
            if "image_model" in metadata:
                cmd.extend(["-set", "comment:image_model", metadata['image_model']])

            # Add timestamp
            if "timestamp" in metadata:
                cmd.extend(["-set", "comment:timestamp", metadata['timestamp']])

            # Add image size/quality if available
            if "image_size" in metadata:
                cmd.extend(["-set", "comment:image_size", metadata['image_size']])

            if "image_quality" in metadata:
                cmd.extend(["-set", "comment:image_quality", metadata['image_quality']])

        # Overwrite the original file
        cmd.append(image_path)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            log(f"Warning: ImageMagick metadata embedding failed: {result.stderr}")
            return False

        log(f"Embedded metadata into {image_path}")
        return True

    except Exception as e:
        log(f"Error embedding metadata: {e}")
        return False

# ============================================================================
# PIPELINE ORCHESTRATION
# ============================================================================

def run_pipeline() -> Dict[str, Any]:
    """Run the complete pipeline: gather → prompt → image → archive → resize → video"""
    pipeline_start = datetime.now()
    log("=" * 60)
    log("STARTING PIPELINE")
    log("=" * 60)

    result = {
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "steps": {}
    }

    # Ensure output directory exists
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Get all HA states and discover location
    # Note: Raw ENTITY_IDS config is shown in ENTITY EXPOSURE section below

    all_states = []
    location_info = {"timezone": "America/Phoenix", "location_name": None}

    if SUPERVISOR_TOKEN:
        try:
            # Get all states from HA
            resp = requests.get(
                f"{SUPERVISOR_API}/states",
                headers={
                    "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            resp.raise_for_status()
            all_states = resp.json()
            log(f"Retrieved {len(all_states)} total states from HA")

            # Discover location info
            location_info = discover_location_info(all_states)
        except Exception as e:
            log(f"Error fetching HA states: {e}")
    else:
        log("Warning: No SUPERVISOR_TOKEN, cannot fetch HA states")

    # Step 2: Process entity config (supports plain IDs, templates, and mixed)
    context = process_entity_config(ENTITY_IDS, all_states)
    result["steps"]["gather_entities"] = {
        "count": len(context),
        "entity_ids": list(context.keys())
    }

    # Log what will be exposed for this generation
    log_entity_exposure(context)

    # Step 3: Generate art prompt
    art_prompt, prompt_metadata = generate_prompt_from_context(context, location_info)
    if not art_prompt:
        result["error"] = "Failed to generate art prompt"
        log("PIPELINE FAILED: No art prompt generated")
        return result

    result["steps"]["generate_prompt"] = {
        "prompt_length": len(art_prompt),
        "prompt": art_prompt,  # Store full prompt, not preview
        "tokens": prompt_metadata.get("tokens", {}),
        "search_count": prompt_metadata.get("search_count", 0),
        "generation_time": prompt_metadata.get("generation_time", 0)
    }

    # Step 4: Generate image (temporary file)
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    temp_filename = f"{FILENAME_PREFIX}_temp.png"

    image_result = generate_image(art_prompt, temp_filename)
    if not image_result or not image_result.get("success"):
        result["error"] = image_result.get("error", "Unknown error")
        log("PIPELINE FAILED: Image generation failed")
        return result

    result["steps"]["generate_image"] = image_result
    temp_image_path = image_result["filepath"]

    # Step 5: Archive original with metadata (if save_original enabled)
    archive_path = None
    if SAVE_ORIGINAL:
        archive_dir = output_path / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        archive_filename = f"{FILENAME_PREFIX}_{timestamp}.png"
        archive_path = str(archive_dir / archive_filename)

        # Copy temp file to archive
        log(f"Archiving original to {archive_path}")
        Path(temp_image_path).rename(archive_path)

        # Embed metadata into archived file
        metadata = {
            "model": IMAGE_MODEL,
            "prompt_model": PROMPT_MODEL,
            "image_model": IMAGE_MODEL,
            "timestamp": timestamp,
            "image_size": IMAGE_SIZE,
            "image_quality": IMAGE_QUALITY
        }
        embed_metadata(archive_path, art_prompt, metadata)

        result["archive"] = archive_path

        # Copy archive to temp for further processing
        import shutil
        shutil.copy2(archive_path, temp_image_path)

    # Step 6: Resize to working image
    working_image_path = str(output_path / f"{FILENAME_PREFIX}.png")

    if RESIZE_OUTPUT:
        resize_result = resize_image(
            temp_image_path,
            working_image_path,
            TARGET_RESOLUTION
        )

        if resize_result and resize_result.get("success"):
            result["steps"]["resize_image"] = resize_result
            result["image"] = working_image_path
            log(f"Generated working image: {working_image_path}")
        else:
            log("WARNING: Resize failed, using original as working image")
            Path(temp_image_path).rename(working_image_path)
            result["image"] = working_image_path
    else:
        # No resize, just move temp to working location
        log("Resize disabled, using original size")
        Path(temp_image_path).rename(working_image_path)
        result["image"] = working_image_path

    # Fire image complete event
    fire_event("post_informer_image_complete", {
        "success": True,
        "image": working_image_path,
        "archive": archive_path,
        "resolution": TARGET_RESOLUTION if RESIZE_OUTPUT else IMAGE_SIZE,
        "timestamp": result["timestamp"]
    })

    # Step 7: Create video (if enabled)
    if ENABLE_VIDEO:
        video_path = str(output_path / f"{FILENAME_PREFIX}.mp4")

        video_result = create_video(working_image_path, video_path)

        if video_result and video_result.get("success"):
            result["steps"]["create_video"] = video_result
            result["video"] = video_path
            result["success"] = True
            log(f"Generated video: {video_path}")

            # Fire video complete event
            fire_event("post_informer_video_complete", {
                "success": True,
                "video": video_path,
                "duration": VIDEO_DURATION,
                "timestamp": result["timestamp"]
            })
        else:
            log("WARNING: Video creation failed")
            result["steps"]["create_video"] = video_result
            result["success"] = True  # Still success if image worked
    else:
        log("Video generation disabled, skipping")
        result["success"] = True

    # Clean up temp file if it still exists
    if Path(temp_image_path).exists():
        Path(temp_image_path).unlink()

    # Pipeline complete
    pipeline_elapsed = (datetime.now() - pipeline_start).total_seconds()
    result["total_time"] = pipeline_elapsed

    log("=" * 60)
    log(f"PIPELINE COMPLETE", timing=pipeline_elapsed)
    log("=" * 60)

    # Show summary of key metrics
    if "generate_prompt" in result["steps"]:
        prompt_step = result["steps"]["generate_prompt"]
        tokens = prompt_step.get("tokens", {})
        search_count = prompt_step.get("search_count", 0)

        if tokens:
            log(f"📊 Prompt Generation - Tokens: {tokens.get('input', 0)} in / {tokens.get('output', 0)} out / {tokens.get('total', 0)} total")
        if search_count > 0:
            log(f"🔍 Web Searches: {search_count} performed")

    if "generate_image" in result["steps"]:
        img_step = result["steps"]["generate_image"]
        log(f"🖼️  Image: {img_step.get('size', 'unknown')} @ {img_step.get('render_time', 0):.2f}s")

    if "resize_image" in result["steps"]:
        resize_step = result["steps"]["resize_image"]
        log(f"📐 Resize: {resize_step.get('resolution', 'unknown')} @ {resize_step.get('resize_time', 0):.2f}s")

    if "create_video" in result["steps"]:
        video_step = result["steps"]["create_video"]
        log(f"🎬 Video: {video_step.get('duration', 0)}s @ {video_step.get('encode_time', 0):.2f}s")

    log("=" * 60)

    # Fire completion event
    fire_event("post_informer_complete", result)

    return result

# ============================================================================
# MAIN
# ============================================================================

def main():
    log("=" * 60)
    log(f"Post Informer v{BUILD_VERSION}")
    log(f"Build: {BUILD_TIMESTAMP}")
    log("=" * 60)
    log("Add-on started, waiting for input...")
    log(f"Config: {PROMPT_MODEL} → {IMAGE_MODEL}")
    log(f"Output: {OUTPUT_DIR}/{FILENAME_PREFIX}_*")
    log(f"Resize: {RESIZE_OUTPUT} ({TARGET_RESOLUTION})")
    log(f"Video: {ENABLE_VIDEO} ({VIDEO_DURATION}s @ {VIDEO_FRAMERATE}fps)")

    # Debug search prompts configuration
    log(f"Search Prompts: {len(SEARCH_PROMPTS)} configured")
    if SEARCH_PROMPTS:
        for i, prompt in enumerate(SEARCH_PROMPTS, 1):
            log(f"  [{i}] {prompt}")
    else:
        # Show raw env var to help debug why it's empty
        raw_value = os.environ.get("SEARCH_PROMPTS", "<not set>")
        log(f"  (SEARCH_PROMPTS env var: {raw_value[:100]})")  # Show first 100 chars

    if not API_KEY:
        log("ERROR: No OpenAI API key configured!")

    # Run startup entity scan for transparency and debugging
    run_startup_entity_scan()

    log("=" * 60)
    log("Ready - waiting for generate commands via stdin...")
    log("=" * 60)

    # Read stdin line by line forever
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            log(f"Invalid JSON: {e}")
            continue

        # Handle both string and dict input
        if isinstance(data, str):
            # If input is a string, treat it as the action
            action = data
        elif isinstance(data, dict):
            # If input is a dict, get the action field
            action = data.get("action", "generate")
        else:
            log(f"Invalid input type: {type(data).__name__}")
            continue

        if action == "generate":
            # Run the pipeline
            result = run_pipeline()

            # Log summary
            if result.get("success"):
                log(f"SUCCESS: Generated {result.get('image')}")
                if result.get("archive"):
                    log(f"SUCCESS: Archived to {result.get('archive')}")
                if result.get("video"):
                    log(f"SUCCESS: Generated {result.get('video')}")
            else:
                log(f"FAILED: {result.get('error', 'Unknown error')}")
        else:
            log(f"Unknown action: {action}")


if __name__ == "__main__":
    main()
