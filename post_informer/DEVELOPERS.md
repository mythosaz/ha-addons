# Developer Documentation

Technical details and advanced customization for Post Informer.

---

## Architecture

### Pipeline Flow

```
User Trigger
    ↓
Gather HA Entities
    ↓
Process Jinja2 Templates
    ↓
Discover Location (zone.home)
    ↓
Generate Prompt (gpt-5.2 + web search)
    ↓
Render Image (gpt-image-1.5)
    ↓
Archive Original (with metadata)
    ↓
Resize Image (ffmpeg)
    ↓
Create Video (ffmpeg)
    ↓
Fire HA Events
```

### Key Components

**generator.py** - Main pipeline orchestration
- Entity gathering via Supervisor API
- Jinja2 template processing
- OpenAI API integration (Responses + Chat Completions)
- Image/video processing
- Event firing

**system_prompt.txt** - Creative direction for image generation
- Loaded at runtime from `/system_prompt.txt`
- Instructs gpt-5.2 on composition style
- References gpt-image-1.5 capabilities

**run.sh** - Entrypoint and environment setup
- Reads bashio config
- Converts YAML lists to JSON
- Exports environment variables
- Launches generator.py

---

## Configuration Parsing

### ENTITY_IDS Parsing

The parser handles multiple formats:

1. **Plain Entity IDs**: `sensor.temp, calendar.events`
2. **Jinja2 Templates**: `{{ states('sensor.temp') }}`
3. **Mixed**: Templates and IDs together
4. **YAML Scalars**: Literal (`|`), folded (`>`), and stripped variants

**Parser Algorithm:**

```python
# Character-by-character parsing
# Tracks template depth with {{ and }}
# Separates templates from plain IDs
# Merges adjacent templates with their labels
```

**Edge Case:** Literal `{{` or `{%` inside Jinja strings will confuse depth counter.
Workaround: Escape braces in strings: `{{ "Price is \\{\\{ value \\}\\}" }}`

### SEARCH_PROMPTS Parsing

**Problem:** `bashio::config` returns YAML lists as newline-separated text, not JSON.

**Solution** (run.sh):
```bash
export SEARCH_PROMPTS="$(bashio::config 'search_prompts' | jq -R -s -c 'split("\n") | map(select(length > 0))')"
```

Converts:
```
national news
local news
```

To:
```json
["national news", "local news"]
```

---

## Jinja2 Template Support

### Available Functions

Mimics Home Assistant's template engine:

```python
states(entity_id)              # Get state value
state_attr(entity_id, attr)    # Get attribute value
is_state(entity_id, state)     # Check state (also available as test)
```

### Available Filters

```python
int(value, default=0)          # Convert to int with fallback
float(value, default=0.0)      # Convert to float with fallback
state_attr(entity_id, attr)    # Also available as filter
```

### Available Tests

```python
is_state(entity_id, state)     # Test if entity in state
```

### States Object

Supports both call and attribute syntax:

```jinja
{{ states('sensor.temp') }}           # Function call
{{ states.sensor.temp.state }}        # Attribute access
{{ states.sensor.temp.attributes }}   # Access attributes object
```

---

## API Integration

### Responses API (Primary)

Used for web search capabilities:

```python
client.responses.create(
    model="gpt-5.2",
    input=[
        {"role": "developer", "content": [...]},
        {"role": "user", "content": [...]}
    ],
    tools=[{
        "type": "web_search",
        "user_location": {"type": "approximate"},
        "search_context_size": "medium"
    }]
)
```

**Output Structure:**
```python
response.output[i].content[j]
  .type = "output_text" | "tool_use" | "tool_result"
  .text = "..." (for output_text)
  .name = "web_search" (for tool_use)
  .input = {"query": "..."} (for tool_use)
```

**Token Usage:**
```python
response.usage.input_tokens
response.usage.output_tokens
response.usage.total_tokens
```

### Chat Completions API (Fallback)

Used when Responses API fails:

```python
client.chat.completions.create(
    model="gpt-5.2",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    max_completion_tokens=4096,
    temperature=1.0
)
```

---

## Custom Prompt Variables

When `use_default_prompts: false`, custom prompts can use these variables:

```python
prompt_variables = {
    "context": json.dumps(transformed_context, indent=2),
    "search_prompts": "\n".join(SEARCH_PROMPTS),
    "default_system_prompt": load_system_prompt(),
    "default_user_prompt": formatted_default_user_prompt,
    "location_name": location_info.get("location_name", "Unknown"),
    "timezone": location_info.get("timezone", "UTC"),
    "prompt_model": PROMPT_MODEL,
    "image_model": IMAGE_MODEL,
}

# Applied via:
system_prompt = CUSTOM_SYSTEM_PROMPT.format(**prompt_variables)
user_prompt = CUSTOM_USER_PROMPT.format(**prompt_variables)
```

**Example Use Case:**

```yaml
custom_user_prompt: |
  {default_user_prompt}

  Additional: Use only {location_name} landmarks.
  Current model: {prompt_model}
```

---

## Context Transformation

Raw entity context is transformed before sending to AI:

```python
# Before:
{
  "{{ big_template }}": {
    "rendered_value": "SUN: 45° | WEATHER: Sunny"
  },
  "sensor.temp": {
    "state": "72",
    "attributes": {"unit": "°F"}
  }
}

# After (transformed_context):
{
  "rendered_template": "SUN: 45° | WEATHER: Sunny",
  "sensor.temp": {
    "state": "72",
    "attributes": {"unit": "°F"}
  }
}
```

**Why?** Cleans up keys and extracts rendered values for cleaner AI input.

---

## Image Generation

### Models

- **gpt-image-1.5**: High-quality image generation
  - Supports `output_format: "png"`
  - Returns base64-encoded PNG
  - 1536x1024 default resolution

- **dall-e-3** (alternative): Older model
  - Uses `response_format: "b64_json"`
  - Lower quality than gpt-image-1.5

### Metadata Embedding

Uses ImageMagick to embed metadata in archived PNGs:

```bash
convert image.png \
  -set "Description" "prompt text" \
  -set "comment:prompt_model" "gpt-5.2" \
  -set "comment:image_model" "gpt-image-1.5" \
  -set "comment:timestamp" "202601050600" \
  image.png
```

View with: `exiftool image.png` or `identify -verbose image.png`

---

## Video Encoding

### Default ffmpeg Settings

```bash
ffmpeg -y \
  -framerate 0.25 \          # Input framerate (1 frame / 4 seconds)
  -loop 1 \                  # Loop the input image
  -i image.png \
  -t 1800 \                  # Duration (30 minutes)
  -c:v libx264 \             # H.264 codec
  -preset ultrafast \        # Speed over compression
  -tune stillimage \         # Optimize for static image
  -pix_fmt yuv420p \         # Compatibility
  -movflags +faststart \     # Enable streaming
  output.mp4
```

**Why ultrafast?** Static images don't benefit from slow encoding - ultrafast is 10x faster with minimal quality loss.

---

## Event Data Structures

### post_informer_complete

Full pipeline event includes:

```json
{
  "success": true,
  "timestamp": "2026-01-05T06:00:00",
  "total_time": 67.42,
  "image": "/media/post_informer/post_informer.png",
  "archive": "/media/post_informer/archive/post_informer_202601050600.png",
  "video": "/media/post_informer/post_informer.mp4",
  "steps": {
    "gather_entities": {
      "count": 8,
      "entity_ids": ["sensor.temp", "calendar.events", ...]
    },
    "generate_prompt": {
      "prompt_length": 2847,
      "prompt": "Full prompt text...",
      "tokens": {
        "input": 1200,
        "output": 800,
        "total": 2000
      },
      "search_count": 2,
      "generation_time": 12.5
    },
    "generate_image": {
      "success": true,
      "filepath": "/media/post_informer/post_informer_temp.png",
      "filename": "post_informer_temp.png",
      "size": "1536x1024",
      "render_time": 42.31
    },
    "resize_image": {
      "success": true,
      "filepath": "/media/post_informer/post_informer.png",
      "resolution": "1920x1080",
      "resize_time": 1.12
    },
    "create_video": {
      "success": true,
      "filepath": "/media/post_informer/post_informer.mp4",
      "duration": 1800,
      "framerate": "0.25",
      "encode_time": 13.21
    }
  }
}
```

---

## Logging Format

All logs follow this format:

```
[post_informer] [YYYY-MM-DD HH:MM:SS] Message (timing)
```

**Timing suffix** is optional and shows elapsed time in seconds:

```
[post_informer] [2026-01-05 06:00:15] Generated prompt (8.94s)
```

**Special prefixes:**
- 🔍 - Web search
- ✓ - Success marker
- ℹ️ - Info
- ❌ - Error
- ⚠️ - Warning
- 📊 - Metrics
- 🖼️ - Image
- 📐 - Resize
- 🎬 - Video

---

## Development Setup

### Local Testing

1. Clone repository
2. Create virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install openai requests jinja2
   ```

3. Set environment variables:
   ```bash
   export OPENAI_API_KEY="sk-..."
   export ENTITY_IDS='sensor.temp'
   export SEARCH_PROMPTS='["national news"]'
   export OUTPUT_DIR="/tmp/post_informer"
   ```

4. Run generator:
   ```bash
   echo '{"action":"generate"}' | python3 generator.py
   ```

### Testing in Home Assistant

Use the add-on developer mode:

1. Mount local directory to `/media/post_informer_dev`
2. Modify `run.sh` to use dev paths
3. Rebuild add-on
4. Check logs in real-time

---

## Performance Optimization

### Token Usage

**Typical consumption per generation:**
- Input tokens: 1000-2000 (depends on entity count and template complexity)
- Output tokens: 500-1000 (depends on prompt length)
- **Total: ~1500-3000 tokens per generation**

With web search enabled, add ~500-1000 tokens per search.

### Caching Opportunities

Consider caching for:
1. **Entity states** - If generating multiple times rapidly
2. **Location info** - Rarely changes
3. **System prompt** - Loaded once at startup

Currently, only system prompt is cached (loaded once in `load_system_prompt()`).

### ffmpeg Optimization

For faster encoding:
- Use `ultrafast` preset (default)
- Lower resolution (480p vs 4K)
- Higher framerate (fewer total frames)

Example for 5-minute video at 480p:
- Encoding time: ~3-5s (vs 10-20s for 1080p)

---

## Troubleshooting

### Template Rendering Fails

**Check:**
1. Jinja2 installed? (`pip list | grep jinja2`)
2. Template syntax valid? (test in HA Developer Tools → Template)
3. Entity IDs exist? (check HA entity registry)

**Debug:**
- Check ENTITY EXPOSURE log section
- Look for ❌ errors in template rendering
- Verify entity IDs match exactly (case-sensitive)

### Search Prompts Not Working

**Check:**
1. YAML list format correct?
   ```yaml
   search_prompts:
     - item 1
     - item 2
   ```
2. Add-on logs show prompts at startup?
3. Web searches logged during generation?

**Debug:**
- Check startup log for "Search Prompts: X configured"
- Look for "🔍 Web Search #N:" in generation logs
- Check "ℹ️ No web searches were triggered" message

### API Failures

**Responses API fails → Chat Completions fallback**

Check logs for:
```
Responses API failed: [error]
Falling back to Chat Completions API...
```

**Both APIs fail:**
- Verify API key is valid
- Check model names (gpt-5.2, gpt-image-1.5)
- Verify API key has access to models
- Check OpenAI API status

---

## API Rate Limits

**OpenAI Tier Limits (example for Tier 3):**

| Model | RPM | TPM | Batch Queue |
|-------|-----|-----|-------------|
| gpt-5.2 | 5,000 | 800,000 | 5,000,000 |
| gpt-image-1.5 | 500 | N/A | N/A |

**Post Informer Usage:**
- 1 generation = 1 gpt-5.2 request + 1 gpt-image-1.5 request
- With search = 1-3 additional requests (search queries)
- **Safe rate: ~50 generations/hour** (tier 3+)

For high-frequency generations (every 5 min = 12/hr), well within limits.

---

## Contributing

### Code Style

- Follow Python PEP 8
- Use type hints where helpful
- Add docstrings for public functions
- Comment complex logic

### Testing Checklist

Before submitting PR:

- [ ] Tested with plain entity IDs
- [ ] Tested with Jinja2 templates
- [ ] Tested with search prompts
- [ ] Tested with custom prompts
- [ ] Checked logs for errors
- [ ] Verified events fire correctly
- [ ] Tested image generation
- [ ] Tested video encoding
- [ ] Updated CHANGELOG.md
- [ ] Updated README.md if needed

---

## Security Considerations

### API Key Handling

- Never log API keys
- Store only in HA add-on config (encrypted at rest)
- Never include in error messages

### Entity Exposure

- ENTITY EXPOSURE log shows what data is sent to OpenAI
- Review this section to understand privacy implications
- Sensitive entities (cameras, locks with codes) should not be included

### Metadata Privacy

Archived images contain:
- Full prompt text (may include entity data)
- Timestamp
- Model names

Consider archival location carefully if privacy is a concern.

---

## Future Enhancements

**Potential improvements:**

1. **Caching Layer**
   - Cache entity states between rapid generations
   - Cache location discovery

2. **Parallel Processing**
   - Generate image and resize concurrently
   - Generate video from temp file while archiving

3. **Retry Logic**
   - Exponential backoff for API failures
   - Automatic retry with fallback models

4. **Advanced Search**
   - Custom search engines (Google, Bing)
   - Search result filtering/ranking

5. **Multi-Image Support**
   - Generate multiple variations
   - A/B testing for best result

---

## License

MIT - See LICENSE file for details.
