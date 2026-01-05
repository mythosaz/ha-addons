#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Post Informer add-on"

# Pass options to Python script via environment
export OPENAI_API_KEY="$(bashio::config 'openai_api_key')"
export DEFAULT_MODEL="$(bashio::config 'default_model')"
export DEFAULT_QUALITY="$(bashio::config 'default_quality')"
export DEFAULT_SIZE="$(bashio::config 'default_size')"
export OUTPUT_DIR="$(bashio::config 'output_dir')"

# Run the generator (reads stdin forever)
exec python3 /generator.py
