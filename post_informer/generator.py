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
BUILD_VERSION = "1.0.5-2026-01-09"
BUILD_TIMESTAMP = "2026-01-09 08:30:00 UTC"

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

DEFAULT_SYSTEM_PROMPT = """
You are an image‑1.5 prompt composer. Your job is to transform structured, banal data into spectacular, narrative‑driven images with wide cultural, visual, and stylistic inspiration.

Your output must be exactly one complete image‑1.5 prompt. No explanations.

CORE GOAL
Invent a strong, independent visual scene first that is NOT a depiction of a smart home, and then selectively smuggle a small amount of data into the world as texture, commentary, or contrast

SUBJECT FIRST (HARD RULE)
The image depicts a world, moment, event, or character in motion or tension.
The scene must not exist to display information.
Interfaces, dashboards, readouts, and text are secondary artifacts, never the reason for the image.
Remove every data element mentally: the image must still read as a film still, illustration, poster, or surreal tableau.
The subject is chosen early and decisively, informed by home / weather / news data only as inspiration, never as raw material.

SCENE CONSTRUCTION (INTERNAL, SILENT)
Build the scene loosely as:
{one vivid modifier or mood} {one or two concrete subjects} {caught in a dynamic or unstable action} while / as / because {one or two pressures or conditions inspired by data}.
Do not mirror user phrasing. Invent freely.
The data’s role is to tilt the world, not describe it.
DATA AS INFLUENCE, NOT INVENTORY
You are allowed to summarize, paraphrase, symbolize, or discard data.
Include only what sharpens tone, irony, or narrative.
Exact values matter only if their legibility adds punch or humor.
Good uses:
Mood (cold, tense, sluggish, overheated, waiting)
Stakes (order vs chaos, vigilance vs intrusion, routine vs rupture)
Texture (labels, signage, props, background ephemera)
Bad uses:
Exhaustive readouts
Recreating dashboards
Turning the image into a status report

DATA PRESENTATION: TWO LAYERS, ONE WORLD (EXPLICIT)
Data may appear in exactly two forms, with explicit description and placement in the final prompt.

1) WOVEN / DIEGETIC ELEMENTS (IN-WORLD)
Describe what the object is, where it is, and what text or symbols it shows.
These elements must plausibly exist in the scene (signs, notes, packaging, screens, reflections, props, artifacts).
Use selectively. Include only items that strengthen tone or story.
Do not force unrelated data into natural objects.

2) DISTINCT HUD / OVERLAY LAYER (ON TOP OF THE SCENE)
You may include one unified HUD / AR / video‑game‑style overlay.
The HUD must be described verbatim and concretely:
visual style (e.g., clean trapezoidal UI, alien glyph borders, CRT glow, AR reticle)
placement (edges, corners, center reticle, floating frame, screen glass)
contents (what data appears, summarized or exact, and any humorous or fictional elements)
The HUD may contain:
real summarized data
symbolic meters or indicators
playful or easter‑egg UI elements (eject button, idle animation, bouncing icon)
Rules for the HUD:
It complements the image; it does not explain it
It does not replace the scene as the subject
It uses one coherent visual language, not mixed widget styles
Both layers must be clearly specified so the image model does not invent layout, wording, or placement. The scene always comes first; the data reacts to it.

STYLE & RANGE (WIDE, INTENTIONAL)
You may blend:
Eras, genres, and materials
High art with trash aesthetics
Surreal, comic, painterly, cinematic, diagrammatic, or folk‑art sensibilities
References are directional, not imitative. Avoid safe defaults. Avoid polite interiors.

AMBITION CHECK (MANDATORY)
Before writing the final prompt, silently confirm:
Is there a clear subject doing something?
Is there tension, absurdity, or narrative imbalance?
Does the data feel discovered, not presented?
Did I take at least one visual or conceptual risk?
If yes, write the prompt.

OUTPUT RULES
Single image‑1.5 prompt only
No bullets, no analysis, no meta
Commit fully to the scene
"""

DEFAULT_USER_PROMPT_TEMPLATE = """Home Assistant data:
{context}

NEWS:
Search the internet for major headlines.{local_news_instruction}
Should the national or local news include important or noteworthy items, consider them for inclusion.

NOTE:
This is a static image. Do not display the actual time. Reflect only in the art.

TASK:
Create exactly one highly detailed unconstrained image-1.5 prompt with no limit - Do not explain your reasoning.
"""

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

    return {
        "states": states_func,
        "state_attr": state_attr_func,
        "is_state": is_state_func,
    }


def process_entity_config(entity_config: Union[str, List[str]], all_states: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process entity_ids config - handles plain IDs, templates, and mixed formats"""
    result = {}

    # Parse into list
    if isinstance(entity_config, list):
        entity_list = entity_config
    else:
        # Support legacy string formats
        entity_list = [e.strip() for e in entity_config.split('\n') if e.strip()]
        if not entity_list or len(entity_list) == 1:
            entity_list = [e.strip() for e in entity_config.split(',') if e.strip()]
        if not entity_list or len(entity_list) == 1:
            entity_list = [e.strip() for e in entity_config.split() if e.strip()]

    # Build state lookup dict
    states_dict = {s.get("entity_id"): s for s in all_states}

    # Separate plain entity IDs from templates
    plain_ids = []
    templates = []

    for item in entity_list:
        item = item.strip()
        if not item:
            continue

        # Check if it's a Jinja2 template
        if re.search(r'\{\{.*?\}\}', item):
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

        for template_str in templates:
            try:
                template = env.from_string(template_str)
                rendered = template.render(jinja_context)
                result[template_str] = {"rendered_value": rendered}
                log(f"Rendered: {template_str[:50]}... -> {rendered}")
            except Exception as e:
                log(f"Error rendering template '{template_str[:50]}...': {e}")
                result[template_str] = {"error": str(e)}
    elif templates and not JINJA2_AVAILABLE:
        log("Warning: Jinja2 templates found but jinja2 library not available")
        for template_str in templates:
            result[template_str] = {"error": "jinja2 not installed"}

    return result

# ============================================================================
# PIPELINE STEPS
# ============================================================================

def generate_prompt_from_context(context: Dict[str, Any], location_info: Dict[str, str]) -> Optional[str]:
    """Call OpenAI to generate an image prompt based on HA context"""
    start_time = datetime.now()

    # Build local news instruction based on location
    local_news_instruction = ""
    if location_info.get("location_name"):
        local_news_instruction = f"\nSearch the internet for local {location_info['location_name']} news."

    # Choose prompts
    if USE_DEFAULT_PROMPTS:
        system_prompt = DEFAULT_SYSTEM_PROMPT
        user_prompt = DEFAULT_USER_PROMPT_TEMPLATE.format(
            context=json.dumps(context, indent=2),
            local_news_instruction=local_news_instruction
        )
    else:
        system_prompt = CUSTOM_SYSTEM_PROMPT
        user_prompt = CUSTOM_USER_PROMPT.format(
            context=json.dumps(context, indent=2),
            local_news_instruction=local_news_instruction
        )

    log(f"Generating art prompt with {PROMPT_MODEL}...")
    log(f"Context size: {len(json.dumps(context))} chars")
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
                            "type": "approximate",
                            "timezone": location_info["timezone"]
                        },
                        "search_context_size": "medium"
                    }
                ],
                store=True
            )

            # Extract the text from the response
            prompt = None
            for item in response.input:
                if item.role == "assistant" and hasattr(item, 'content'):
                    for content_item in item.content:
                        if content_item.type == "output_text":
                            prompt = content_item.text.strip()
                            break
                if prompt:
                    break

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

        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Generated prompt ({len(prompt)} chars)", timing=elapsed)
        log("=" * 60)
        log("FULL PROMPT FOR IMAGE GENERATION:")
        log("=" * 60)
        log(prompt)
        log("=" * 60)

        return prompt

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        log(f"Error generating prompt: {e}", timing=elapsed)
        return None


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
    log(f"Raw ENTITY_IDS config: {repr(ENTITY_IDS)}")

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

    # Step 3: Generate art prompt
    art_prompt = generate_prompt_from_context(context, location_info)
    if not art_prompt:
        result["error"] = "Failed to generate art prompt"
        log("PIPELINE FAILED: No art prompt generated")
        return result

    result["steps"]["generate_prompt"] = {
        "prompt_length": len(art_prompt),
        "prompt": art_prompt  # Store full prompt, not preview
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

    if not API_KEY:
        log("ERROR: No OpenAI API key configured!")

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
