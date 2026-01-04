#!/usr/bin/env python3
"""
OpenAI Image Generator for Home Assistant
Reads JSON from stdin, generates images via OpenAI API, writes to /media
"""

import sys
import os
import json
import base64
import requests
from pathlib import Path
from datetime import datetime
from openai import OpenAI

# Config from environment (set by run.sh from add-on options)
API_KEY = os.environ.get("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "gpt-image-1")
DEFAULT_QUALITY = os.environ.get("DEFAULT_QUALITY", "high")
DEFAULT_SIZE = os.environ.get("DEFAULT_SIZE", "1536x1024")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/media/generated")

# Supervisor API for firing events
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
SUPERVISOR_API = "http://supervisor/core/api"


def log(msg: str):
    """Print to stdout for HA logs"""
    print(f"[openai_image] {msg}", flush=True)


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
        log(f"Fired event {event_type}: {resp.status_code}")
    except Exception as e:
        log(f"Error firing event: {e}")


def generate_image(prompt: str, filename: str = None, model: str = None,
                   quality: str = None, size: str = None) -> dict:
    """
    Generate image via OpenAI API and save to output directory.
    Implements versioning: saves both timestamped and current versions.
    """

    model = model or DEFAULT_MODEL
    quality = quality or DEFAULT_QUALITY
    size = size or DEFAULT_SIZE

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"generated_{timestamp}.png"

    # Ensure output directory exists
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    # Create timestamp for versioning: YYYYMMDDHHMM-filename
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    name_parts = filename.rsplit('.', 1)
    if len(name_parts) == 2:
        base_name, ext = name_parts
        timestamped_filename = f"{timestamp}-{base_name}.{ext}"
    else:
        timestamped_filename = f"{timestamp}-{filename}"

    # Two file paths: timestamped archive + current
    timestamped_filepath = output_path / timestamped_filename
    current_filepath = output_path / filename

    log(f"Generating image: model={model}, quality={quality}, size={size}")
    log(f"Prompt: {prompt[:100]}...")
    log(f"Will save as: {timestamped_filename} (archived) and {filename} (current)")

    start_time = datetime.now()

    try:
        client = OpenAI(api_key=API_KEY)

        # GPT image models don't use response_format - they always return b64_json
        # Use output_format for file type (png/jpeg/webp)
        generate_params = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality,
        }

        # output_format only supported for gpt-image models
        if "gpt-image" in model:
            generate_params["output_format"] = "png"
        else:
            # DALL-E models use response_format
            generate_params["response_format"] = "b64_json"

        response = client.images.generate(**generate_params)

        render_time = (datetime.now() - start_time).total_seconds()
        log(f"render_time_seconds: {render_time:.2f}")

        # Decode image data
        image_data = base64.b64decode(response.data[0].b64_json)

        # Save timestamped version (for archive)
        timestamped_filepath.write_bytes(image_data)
        log(f"Archived: {timestamped_filepath}")

        # Save current version (for rendering/display)
        current_filepath.write_bytes(image_data)
        log(f"Current: {current_filepath}")

        return {
            "success": True,
            "filepath": str(current_filepath),
            "filepath_archived": str(timestamped_filepath),
            "filename": filename,
            "filename_archived": timestamped_filename,
            "model": model,
            "size": size,
            "render_time_seconds": render_time
        }

    except Exception as e:
        render_time = (datetime.now() - start_time).total_seconds()
        log(f"render_time_seconds: {render_time:.2f}")
        log(f"Error generating image: {e}")
        return {
            "success": False,
            "error": str(e),
            "render_time_seconds": render_time
        }


def main():
    log("Add-on started, waiting for input...")

    if not API_KEY:
        log("ERROR: No OpenAI API key configured!")
        # Don't exit - keep running so HA doesn't restart us endlessly

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

        # Get prompt from either direct prompt or prompt_file
        prompt = data.get("prompt")
        prompt_file = data.get("prompt_file")

        if not prompt and not prompt_file:
            log("No prompt or prompt_file provided, skipping")
            continue

        # If prompt_file specified, read from file
        if prompt_file and not prompt:
            try:
                with open(prompt_file, 'r') as f:
                    prompt = f.read().strip()
                log(f"Read prompt from file: {prompt_file}")
            except FileNotFoundError:
                log(f"ERROR: Prompt file not found: {prompt_file}")
                continue
            except Exception as e:
                log(f"ERROR: Failed to read prompt file: {e}")
                continue

        if not prompt:
            log("Prompt is empty, skipping")
            continue

        # Generate the image
        result = generate_image(
            prompt=prompt,
            filename=data.get("filename"),
            model=data.get("model"),
            quality=data.get("quality"),
            size=data.get("size")
        )

        # Fire HA event with result
        fire_event("openai_image_complete", {
            **result,
            "prompt_preview": prompt[:100]
        })


if __name__ == "__main__":
    main()