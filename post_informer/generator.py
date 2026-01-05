#!/usr/bin/env python3
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

# Version info
BUILD_VERSION = "1.0.0-2026-01-05"
BUILD_TIMESTAMP = "2026-01-05 10:30:00 UTC"

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
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/media/generated")
FILENAME_PREFIX = os.environ.get("FILENAME_PREFIX", "hud_display")

# Supervisor API
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
SUPERVISOR_API = "http://supervisor/core/api"

# ============================================================================
# DEFAULT PROMPTS
# ============================================================================

DEFAULT_SYSTEM_PROMPT = """
ROLE:
You synthesize data from Home Assistant to create informative and creative prompts to create a futuristic smart "HUD" type display comprised of (a) a background image composed from the "vibe" of the Home Assistant data, and (b) "HUD" information derived from the Home Assistant data.

CORE PARADIGM:
- The scene should be inspired by the data as a whole.
- Use judgment to decide what data matters today.
- "HUD" data should also be woven into the scene.
- Key information should be legible at a distance.
- Secondary or decorative information may be small, stylized, or subtle.

IMPORTANT: Your output must be a single, detailed image-1.5 prompt only. Do not include any explanations, justifications, or commentary. The prompt should stand alone as instructions for generating the image.

VISUAL STYLE FREEDOM:
**DO NOT PICK DIRECTLY FROM THIS LIST**
Draw inspiration from any visual universe—whether it's radiant vaporwave cityscapes, whimsical 1950s sci-fi comics, lush Miyazaki-inspired dreamlands, kinetic cyberpunk marketplaces, serene Art Deco sunlit atriums, surrealist neon jungles, kinetic Bauhaus abstraction, but make it something entirely original. Blend, remix, or invent new aesthetics inspired but not directly contained among this list.

Embrace bold, creative styles that transcend the ordinary, using the full spectrum and dynamic range of a QLED display for maximum visual impact.

DETAIL:
- Image 1.5 can accept your fine details, and the prompt may be as large and refined as necessary.

OUTPUT:
- Produce exactly one highly detailed unconstrained image-1.5 prompt with no limits.
- Do not explain or justify choices.
"""

DEFAULT_USER_PROMPT_TEMPLATE = """Home Assistant data:
{context}

NEWS:
Search the internet for major headlines.
Search the internet for local Phoenix news.
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
            log(f"WARNING: Could not find {len(missing)} entities: {missing}")

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
        log(f"Prompt preview: {prompt[:200]}...")

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
    log(f"Prompt: {prompt[:100]}...")

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

# ============================================================================
# PIPELINE ORCHESTRATION
# ============================================================================

def run_pipeline() -> Dict[str, Any]:
    """Run the complete pipeline: gather → prompt → image → resize → video"""
    pipeline_start = datetime.now()
    log("=" * 60)
    log("STARTING PIPELINE")
    log("=" * 60)

    result = {
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "steps": {}
    }

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
        "prompt_preview": art_prompt[:200]
    }

    # Step 3: Generate image
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    original_filename = f"{FILENAME_PREFIX}_{timestamp}_original.png"

    image_result = generate_image(art_prompt, original_filename)
    if not image_result or not image_result.get("success"):
        result["error"] = image_result.get("error", "Unknown error")
        log("PIPELINE FAILED: Image generation failed")
        return result

    result["steps"]["generate_image"] = image_result
    result["image_original"] = image_result["filepath"]

    # Step 4: Resize image (if enabled)
    resized_filepath = None
    if RESIZE_OUTPUT:
        resized_filename = f"{FILENAME_PREFIX}_{timestamp}_{TARGET_RESOLUTION}.png"
        resized_filepath = str(Path(OUTPUT_DIR) / resized_filename)

        resize_result = resize_image(
            image_result["filepath"],
            resized_filepath,
            TARGET_RESOLUTION
        )

        if resize_result and resize_result.get("success"):
            result["steps"]["resize_image"] = resize_result
            result["image_resized"] = resized_filepath

            # Fire image complete event
            fire_event("post_informer_image_complete", {
                "success": True,
                "image_original": image_result["filepath"],
                "image_resized": resized_filepath,
                "resolution": TARGET_RESOLUTION,
                "timestamp": result["timestamp"]
            })
        else:
            log("WARNING: Resize failed, continuing with original")
            result["steps"]["resize_image"] = resize_result
    else:
        log("Resize disabled, skipping")
        fire_event("post_informer_image_complete", {
            "success": True,
            "image_original": image_result["filepath"],
            "timestamp": result["timestamp"]
        })

    # Step 5: Create video (if enabled)
    if ENABLE_VIDEO:
        # Use resized image if available, otherwise original
        video_source = resized_filepath if resized_filepath else image_result["filepath"]
        video_filename = f"{FILENAME_PREFIX}_{timestamp}.mp4"
        video_filepath = str(Path(OUTPUT_DIR) / video_filename)

        video_result = create_video(video_source, video_filepath)

        if video_result and video_result.get("success"):
            result["steps"]["create_video"] = video_result
            result["video"] = video_filepath
            result["success"] = True

            # Fire video complete event
            fire_event("post_informer_video_complete", {
                "success": True,
                "video": video_filepath,
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
                log(f"SUCCESS: Generated {result.get('image_resized', result.get('image_original'))}")
                if result.get("video"):
                    log(f"SUCCESS: Generated {result.get('video')}")
            else:
                log(f"FAILED: {result.get('error', 'Unknown error')}")
        else:
            log(f"Unknown action: {action}")


if __name__ == "__main__":
    main()
