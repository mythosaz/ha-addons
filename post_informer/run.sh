#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Post Informer add-on"

# API Configuration
export OPENAI_API_KEY="$(bashio::config 'openai_api_key')"
export PROMPT_MODEL="$(bashio::config 'prompt_model')"
export IMAGE_MODEL="$(bashio::config 'image_model')"

# Entity Monitoring
export ENTITY_IDS="$(bashio::config 'entity_ids')"

# Prompt Customization
export USE_DEFAULT_PROMPTS="$(bashio::config 'use_default_prompts')"
export CUSTOM_SYSTEM_PROMPT="$(bashio::config 'custom_system_prompt')"
export CUSTOM_USER_PROMPT="$(bashio::config 'custom_user_prompt')"
# Handle search_prompts - default to empty array if not set or invalid
SEARCH_PROMPTS_RAW="$(bashio::config 'search_prompts' || echo '[]')"
# Suppress jq errors and fallback to empty array if parsing fails
export SEARCH_PROMPTS="$(echo "${SEARCH_PROMPTS_RAW}" | jq -c '.' 2>/dev/null || echo '[]')"

# Image Configuration
export IMAGE_QUALITY="$(bashio::config 'image_quality')"
export IMAGE_SIZE="$(bashio::config 'image_size')"

# Resize Configuration
export RESIZE_OUTPUT="$(bashio::config 'resize_output')"
export TARGET_RESOLUTION="$(bashio::config 'target_resolution')"
export SAVE_ORIGINAL="$(bashio::config 'save_original')"

# Video Configuration
export ENABLE_VIDEO="$(bashio::config 'enable_video')"
export VIDEO_DURATION="$(bashio::config 'video_duration')"
export VIDEO_FRAMERATE="$(bashio::config 'video_framerate')"
export USE_DEFAULT_FFMPEG="$(bashio::config 'use_default_ffmpeg')"
export CUSTOM_FFMPEG_ARGS="$(bashio::config 'custom_ffmpeg_args')"

# Output
export OUTPUT_DIR="$(bashio::config 'output_dir')"
export FILENAME_PREFIX="$(bashio::config 'filename_prefix')"

# Run the generator (reads stdin forever)
exec python3 /generator.py
