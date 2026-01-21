#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Post Informer add-on"

# API Configuration
export OPENAI_API_KEY="$(bashio::config 'openai_api_key')"
export IMAGE_MODEL="$(bashio::config 'image_model')"

# 3-Step Pipeline Models
export SCENE_CONCEPT_MODEL="$(bashio::config 'scene_concept_model')"
export DATA_INTEGRATION_MODEL="$(bashio::config 'data_integration_model')"

# Entity Monitoring
export ENTITY_IDS="$(bashio::config 'entity_ids')"

# Prompt Customization
export SCENE_CONCEPT_SYSTEM_PROMPT="$(bashio::config 'scene_concept_system_prompt')"
export SCENE_CONCEPT_USER_PROMPT="$(bashio::config 'scene_concept_user_prompt')"
export DATA_INTEGRATION_SYSTEM_PROMPT="$(bashio::config 'data_integration_system_prompt')"
export DATA_INTEGRATION_USER_PROMPT="$(bashio::config 'data_integration_user_prompt')"
# Handle search_prompts - build JSON array from YAML list
if bashio::config.has_value 'search_prompts'; then
    # bashio returns list items one per line, convert to JSON array
    export SEARCH_PROMPTS="$(bashio::config 'search_prompts' | jq -R -s -c 'split("\n") | map(select(length > 0))')"
else
    export SEARCH_PROMPTS="[]"
fi

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
