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
# Validate and parse search_prompts with better error handling
if [ -z "${SEARCH_PROMPTS_RAW}" ] || [ "${SEARCH_PROMPTS_RAW}" = "null" ]; then
    bashio::log.debug "search_prompts is empty or null, using empty array"
    export SEARCH_PROMPTS="[]"
else
    # Try to parse with jq
    SEARCH_PROMPTS_PARSED="$(echo "${SEARCH_PROMPTS_RAW}" | jq -c '.' 2>&1)"
    if [ $? -eq 0 ]; then
        export SEARCH_PROMPTS="${SEARCH_PROMPTS_PARSED}"
        bashio::log.debug "search_prompts parsed successfully: ${SEARCH_PROMPTS}"
    else
        bashio::log.warning "Failed to parse search_prompts, using empty array. Raw value: ${SEARCH_PROMPTS_RAW}"
        bashio::log.warning "jq error: ${SEARCH_PROMPTS_PARSED}"
        export SEARCH_PROMPTS="[]"
    fi
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
