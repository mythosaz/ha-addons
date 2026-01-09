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
from pathlib import Path
from datetime import datetime
from openai import OpenAI
from typing import Dict, List, Optional, Any

# Ensure UTF-8 output for proper character encoding
sys.stdout.reconfigure(encoding='utf-8')

# Version info
BUILD_VERSION = "1.0.2-2026-01-08"
BUILD_TIMESTAMP = "2026-01-08 02:00:00 UTC"

# ============================================================================
# CONFIGURATION FROM ENVIRONMENT
# ============================================================================

# API Configuration
API_KEY = os.environ.get("OPENAI_API_KEY", "")
PROMPT_MODEL = os.environ.get("PROMPT_MODEL", "gpt-4o")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-1.5")

# Entity Monitoring
ENTITY_IDS = os.environ.get("ENTITY_IDS", "")

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
You are an image-1.5 prompt composer whose job is to turn banal structured data into ambitious, surprising visual scenes.

Your output must be exactly one detailed image-1.5 prompt, with no explanations.

CORE DIRECTIVE (READ CAREFULLY)
Your goal is to invent a striking visual scene and then weave selected data into that scene in clever, diegetic, or symbolic ways (HUDs, signage, reflections, labels, portals, inscriptions, graffiti, dashboards, magical artifacts, billboards, instruments, AR overlays, etc.).
If the image would still be interesting without the data, you are doing it right.

## SUBJECT DOMINANCE (HARD RULE)
The image must depict a **scene that exists independently of the HUD**.
- The primary subject is **never** the HUD, display, panel, slab, crystal, interface, or information artifact.
- The primary subject must be a **world, event, character, or situation** that implies motion, tension, imbalance, or narrative.
- If all HUD elements were removed, the image should still read as a compelling still from a film, illustration, cartoon, documentary, poster, advertisement, etc.
The HUD may annotate, intrude upon, interrupt, decorate, or argue with the scene — but it must **not justify the scene’s existence**.
If the image exists primarily to show information, the result is incorrect.

SCENE GENERATION (MANDATORY, INTERNAL)
Silently construct the image using this loose Mad-Libs pattern:
{one or two modifiers} {one or two concrete subjects} {doing or undergoing something dynamic or unstable}, while / as / because {one or two pressures, tensions, or conditions inspired by news, weather, or home state} influence the world.
Examples of structure (not content):
“A decaying ___ and a jubilant ___ colliding as ___”
“A serene ___ slowly being overtaken by ___”
“An absurd ___ attempting to maintain order while ___ fails”
You must choose the subject and action yourself. Do not mirror the user’s wording.

STYLE SELECTION (UNINHIBITED, BUT INTENTIONAL)
You may:
reference artists, movements, or aesthetics sparingly and deliberately
blend eras, materials, and visual languages
be playful, surreal, cartoonish, painterly, architectural, graphic, or painterly
You must avoid literal pastiche. References are directional, not imitative.
Good:
“cubist fragmentation meets cheap roadside sign painting”
“Escher-like spatial recursion rendered as office stationery”
“Picasso-era abstraction filtered through mass-produced plastic”
Bad:
“in the style of Picasso”
“exactly like Escher”

HUD / DATA WEAVING (CRITICAL)
Data must appear inside the world, not floating above it.
Acceptable integrations include (examples, not limits):
post-it notes, chalkboards, receipts, tattoos, instrument dials
alien crystals, magical runes, cockpit glass, shop windows
ticker tape, newspaper banners, subway signs, cereal boxes
reflections in mirrors, goggles, visors, puddles, glass
AR overlays, portals, spell circles, control panels, scoreboards

Rules:
Selectively include data. Discard anything that doesn’t strengthen the image.
Weather, news, and HA state should bias mood, color, geometry, or tension, not become charts.
Exact text matters only when it is clearly meant to be read.

AMBITION & RISK (HARD REQUIREMENT)
You are explicitly expected to:
be weird, be funny, be symbolic, be slightly absurd, be visually loud or conceptually dense

You are not allowed to:
default to “clean modern interior with a panel”, play safe, reduce the scene to “a nice display”, If the result could hang in a gallery or appear on a billboard or make someone laugh in confusion, you are on the right track.

DISPLAY CONTEXT (ABSTRACTED)
Assume the image will be shown on a high-contrast, high-resolution display.
Do not depict the display itself unless it meaningfully serves the scene.

OUTPUT CONSTRAINTS
Single image-1.5 prompt
No analysis
No bullet explanations
No restating of user instructions
No safety hedging
Commit to the scene
Mental check before output (silent):
Is there a clear subject doing something?
Would this be interesting without the HUD?
Does the data feel smuggled into the world, not stapled on?
Did I take at least one creative risk?
If yes, write the prompt.
"""

DEFAULT_USER_PROMPT_TEMPLATE = """Home Assistant data:
{context}

NEWS:
Search the local and national news.
Include any relevant, breaking or interesting news in the image.

OUTPUT REQUIREMENT
Return exactly one detailed image-1.5 prompt.
Do not explain your reasoning.
Do not restate this prompt.
Do not play it safe.
Commit to the scene.

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

# ============================================================================
# PIPELINE STEPS
# ============================================================================

def generate_prompt_from_context(context: Dict[str, Any]) -> Optional[str]:
    """Call OpenAI to generate an image prompt based on HA context"""
    start_time = datetime.now()

    # Choose prompts
    if USE_DEFAULT_PROMPTS:
        system_prompt = DEFAULT_SYSTEM_PROMPT
        user_prompt = DEFAULT_USER_PROMPT_TEMPLATE.format(
            context=json.dumps(context, indent=2)
        )
    else:
        system_prompt = CUSTOM_SYSTEM_PROMPT
        user_prompt = CUSTOM_USER_PROMPT.format(
            context=json.dumps(context, indent=2)
        )

    log(f"Generating art prompt with {PROMPT_MODEL}...")
    log(f"Context size: {len(json.dumps(context))} chars")

    try:
        # Note: Using the Responses API format from user's example
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

        data = {
            "model": PROMPT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 4096,
            "temperature": 1.0,
        }

        resp = requests.post(url, headers=headers, json=data, timeout=120)
        resp.raise_for_status()
        result = resp.json()

        prompt = result["choices"][0]["message"]["content"].strip()

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
    log("=" * 60)
    log("PROMPT FOR IMAGE GENERATION:")
    log("=" * 60)
    log(prompt)
    log("=" * 60)

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

    # Step 1: Gather HA entities
    log(f"Raw ENTITY_IDS config: {repr(ENTITY_IDS)}")

    # Parse entity IDs - support multiple formats:
    # - Newline separated
    # - Comma separated
    # - Space separated (YAML folded scalar >- converts newlines to spaces)
    entity_list = [e.strip() for e in ENTITY_IDS.split('\n') if e.strip()]
    if not entity_list or len(entity_list) == 1:
        # Try comma-separated
        entity_list = [e.strip() for e in ENTITY_IDS.split(',') if e.strip()]
    if not entity_list or len(entity_list) == 1:
        # Try space-separated (YAML folded scalars)
        entity_list = [e.strip() for e in ENTITY_IDS.split() if e.strip()]

    log(f"Parsed {len(entity_list)} entity IDs from config")

    context = gather_ha_entities(entity_list)
    result["steps"]["gather_entities"] = {
        "count": len(context),
        "entity_ids": list(context.keys())
    }

    # Step 2: Generate art prompt
    art_prompt = generate_prompt_from_context(context)
    if not art_prompt:
        result["error"] = "Failed to generate art prompt"
        log("PIPELINE FAILED: No art prompt generated")
        return result

    result["steps"]["generate_prompt"] = {
        "prompt_length": len(art_prompt),
        "prompt": art_prompt  # Store full prompt, not preview
    }

    # Step 3: Generate image (temporary file)
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    temp_filename = f"{FILENAME_PREFIX}_temp.png"

    image_result = generate_image(art_prompt, temp_filename)
    if not image_result or not image_result.get("success"):
        result["error"] = image_result.get("error", "Unknown error")
        log("PIPELINE FAILED: Image generation failed")
        return result

    result["steps"]["generate_image"] = image_result
    temp_image_path = image_result["filepath"]

    # Step 4: Archive original with metadata (if save_original enabled)
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

    # Step 5: Resize to working image
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

    # Step 6: Create video (if enabled)
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
