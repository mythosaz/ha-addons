# Post Informer
AI-powered HUD display generator for Home Assistant - turns your banal HA data into stunning visual displays.


## Features
- ✨ **Web Search Integration** - AI searches current news during generation
- 🌍 **Location Auto-Discovery** - Detects timezone and location automatically
- 🔧 **Jinja2 Template Support** - Use templates in entity_ids for dynamic data
- 📊 **Token Usage Tracking** - Monitor AI token consumption
- 🎨 **Custom Prompts** - Extend or replace default prompts with template variables
- ⚡ **No Timeout Limits** - Runs as persistent service
- 📁 **Archival System** - Saves originals with embedded metadata
- 🎬 **Video Generation** - Creates looping videos for displays

## How It Works

**Gather** entities from HA → **Process** Jinja templates → **Generate** AI prompt with web search → **Render** image → **Create** video

_(~60-90s total)_

---

## Quick Start

**Install:**
- Add repository: `https://github.com/mythosaz/ha-addons`
- Install "Post Informer" add-on
- Configure your API key and entity IDs
- Start the add-on

**Trigger Generation:**
```yaml
service: hassio.addon_stdin
data:
  addon: ADDON_SLUG_post_informer
  input:
    action: "generate"
```

**Outputs:**
- `/media/post_informer/post_informer.png` - Current display image
- `/media/post_informer/post_informer.mp4` - Current display video
- `/media/post_informer/archive/` - Timestamped originals with metadata


---

## Configuration

### Minimal Setup

```yaml
openai_api_key: "sk-your-api-key-here"
entity_ids: |
  sensor.weather_temperature
  calendar.family
```

### Full Configuration

<details>
<summary>Click to expand full configuration options</summary>

```yaml
# API Configuration
openai_api_key: "sk-your-api-key-here"
prompt_model: "gpt-5.2"
image_model: "gpt-image-1.5"

# Entity Monitoring
entity_ids: |
  sensor.weather_temperature
  calendar.family
  {{ states('lock.front_door') }}

# Prompt Customization
use_default_prompts: true
custom_system_prompt: ""
custom_user_prompt: ""
search_prompts:
  - national news of major importance
  - local weather alerts

# Image Configuration
image_quality: "high"
image_size: "1536x1024"

# Resize Configuration
resize_output: true
target_resolution: "1080p"
save_original: true

# Video Configuration
enable_video: true
video_duration: 1800
video_framerate: "0.25"
use_default_ffmpeg: true

# Output
output_dir: "/media/post_informer"
filename_prefix: "post_informer"
```
</details>

---

## Configuration Reference

### API Settings

| Option | Default | Description |
|--------|---------|-------------|
| `openai_api_key` | *required* | Your OpenAI API key |
| `prompt_model` | `gpt-5.2` | Model for generating art prompts |
| `image_model` | `gpt-image-1.5` | Model for rendering images |

### Entity Monitoring

**entity_ids** - Entities or templates to monitor

Supports multiple formats:

```yaml
# Plain entity IDs (recommended for full data)
entity_ids: |
  sensor.weather_temperature
  calendar.family
  lock.front_door

# With Jinja2 templates (for formatted values)
entity_ids: |
  SUN: {{ state_attr('sun.sun', 'elevation') }}°
  TEMP: {{ states('sensor.temperature') }}°F
  LOCK: {{ states('lock.front_door') }}

# One giant template (like your example)
entity_ids: >
  {%- set temp = states('sensor.weather') -%}
  WEATHER: {{temp}}°F
```

### Prompt Customization

| Option | Default | Description |
|--------|---------|-------------|
| `use_default_prompts` | `true` | Use built-in HUD-style prompts |
| `custom_system_prompt` | `""` | Override system prompt |
| `custom_user_prompt` | `""` | Override user prompt |
| `search_prompts` | `[]` | List of web search queries |

**Template Variables for Custom Prompts:**

When creating custom prompts, use these placeholders:

| Variable | Description | Example |
|----------|-------------|---------|
| `{context}` | JSON entity data | `{"rendered_template": "SUN: 45°..."}` |
| `{search_prompts}` | Search queries | `national news\nlocal news` |
| `{default_system_prompt}` | Built-in system prompt | Use to extend default |
| `{default_user_prompt}` | Built-in user prompt | Use to extend default |
| `{location_name}` | Auto-discovered location | `Home` |
| `{timezone}` | Auto-discovered timezone | `America/Phoenix` |
| `{prompt_model}` | Prompt model name | `gpt-5.2` |
| `{image_model}` | Image model name | `gpt-image-1.5` |

**Example: Extend Default Prompt**
```yaml
use_default_prompts: false
custom_user_prompt: |
  {default_user_prompt}

  Additional requirement: Use only space themes.
```

**Example: Custom Prompt with Variables**
```yaml
use_default_prompts: false
custom_system_prompt: "You create minimalist art."
custom_user_prompt: |
  Create art for {location_name} ({timezone}):
  {context}

  Search these topics:
  {search_prompts}
```

### Image, Resize & Video Settings

Defaults are recommended for most use cases.

<details>
<summary>Click to expand image/video configuration options</summary>

**Image Settings:**

| Option | Default | Description |
|--------|---------|-------------|
| `image_quality` | `high` | OpenAI quality: `low`, `medium`, `high`, `auto` |
| `image_size` | `1536x1024` | Image dimensions |

**Resize Settings:**

| Option | Default | Description |
|--------|---------|-------------|
| `resize_output` | `true` | Enable image resizing |
| `target_resolution` | `1080p` | `4k`, `1080p`, `720p`, `480p`, or `WIDTHxHEIGHT` |
| `save_original` | `true` | Archive original with metadata |

**Video Settings:**

| Option | Default | Description |
|--------|---------|-------------|
| `enable_video` | `true` | Create video from image |
| `video_duration` | `1800` | Video length in seconds |
| `video_framerate` | `0.25` | Framerate (fractional OK) |
| `use_default_ffmpeg` | `true` | Use built-in ffmpeg settings |
| `custom_ffmpeg_args` | `""` | Custom ffmpeg args (advanced) |

</details>

### Output Settings

| Option | Default | Description |
|--------|---------|-------------|
| `output_dir` | `/media/post_informer` | Where to save files |
| `filename_prefix` | `post_informer` | Prefix for filenames |

---

## Usage Examples

<details>
<summary>Click to expand automation examples</summary>

### Schedule Daily Generation

```yaml
automation:
  - alias: "Morning HUD Display"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: hassio.addon_stdin
        data:
          addon: ADDON_SLUG_post_informer
          input:
            action: "generate"
```

### Update on Events

```yaml
automation:
  - alias: "Update on Calendar Changes"
    trigger:
      - platform: state
        entity_id: calendar.family
    action:
      - service: hassio.addon_stdin
        data:
          addon: ADDON_SLUG_post_informer
          input:
            action: "generate"
```

### Display When Ready

```yaml
automation:
  - alias: "Show on Living Room TV"
    trigger:
      - platform: event
        event_type: post_informer_video_complete
    condition:
      - "{{ trigger.event.data.success }}"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.living_room_tv
        data:
          media_content_id: "{{ trigger.event.data.video }}"
          media_content_type: "video/mp4"
```

</details>

---

## Events

The add-on fires three event types for automation: `post_informer_image_complete`, `post_informer_video_complete`, and `post_informer_complete`.

<details>
<summary>Click to expand event data structures</summary>

### post_informer_image_complete

Fires when image generation completes.

```json
{
  "success": true,
  "image": "/media/post_informer/post_informer.png",
  "archive": "/media/post_informer/archive/post_informer_202601050600.png",
  "resolution": "1080p",
  "timestamp": "2026-01-05T06:00:00"
}
```

### post_informer_video_complete

Fires when video encoding completes.

```json
{
  "success": true,
  "video": "/media/post_informer/post_informer.mp4",
  "duration": 1800,
  "timestamp": "2026-01-05T06:00:00"
}
```

### post_informer_complete

Fires when entire pipeline completes.

```json
{
  "success": true,
  "timestamp": "2026-01-05T06:00:00",
  "image": "/media/post_informer/post_informer.png",
  "video": "/media/post_informer/post_informer.mp4",
  "total_time": 67.42,
  "steps": {
    "generate_prompt": {
      "tokens": {"input": 1200, "output": 800, "total": 2000},
      "search_count": 2,
      "generation_time": 12.5
    },
    "generate_image": {...},
    "resize_image": {...},
    "create_video": {...}
  }
}
```

</details>

---

## File Outputs

```
/media/post_informer/
  post_informer.png      # Working image (resized, always updated)
  post_informer.mp4      # Working video (always updated)

  archive/               # Timestamped originals (if save_original enabled)
    post_informer_202601050600.png
    post_informer_202601051200.png
    ...
```

**Working files** (`*.png`, `*.mp4`) are always overwritten - easy to reference in automations.

**Archive files** preserve generation history with embedded metadata (prompt, model, timestamp).

---

## Pipeline

The add-on runs this pipeline on each generation:

1. **Gather Context** - Fetches HA entity states
2. **Discover Location** - Auto-detects timezone/location from `zone.home`
3. **Generate Prompt** - Uses gpt-5.2 with web search for news integration
4. **Render Image** - Uses gpt-image-1.5 to create high-res image
5. **Archive** - Saves original with metadata (optional)
6. **Resize** - Scales to target resolution (optional)
7. **Create Video** - Converts to looping video (optional)
8. **Fire Events** - Notifies HA of completion

**Typical Timing:**
- Prompt generation: 5-15s
- Image rendering: 30-60s
- Resize: <2s
- Video encoding: 10-20s
- **Total: ~60-90s**

---

## Logs

View detailed logs in the add-on log viewer:

```
[post_informer] [2026-01-05 06:00:05] STARTING PIPELINE
[post_informer] [2026-01-05 06:00:05] Gathered 8 entities (0.82s)
[post_informer] [2026-01-05 06:00:06] Search prompts in request: 2
[post_informer] [2026-01-05 06:00:06]   [1] national news of major importance
[post_informer] [2026-01-05 06:00:06]   [2] local phoenix news
[post_informer] [2026-01-05 06:00:08] 🔍 Web Search #1: latest national news 2026
[post_informer] [2026-01-05 06:00:10] 🔍 Web Search #2: phoenix news today
[post_informer] [2026-01-05 06:00:15] ✓ Total web searches performed: 2
[post_informer] [2026-01-05 06:00:15] Generated prompt (2847 chars) (8.94s)
[post_informer] [2026-01-05 06:00:58] Image rendered (42.31s)
[post_informer] [2026-01-05 06:01:12] PIPELINE COMPLETE (67.42s)
[post_informer] [2026-01-05 06:01:12] 📊 Tokens: 1200 in / 800 out / 2000 total
[post_informer] [2026-01-05 06:01:12] 🔍 Web Searches: 2 performed
[post_informer] [2026-01-05 06:01:12] 🖼️  Image: 1536x1024 @ 42.31s
[post_informer] [2026-01-05 06:01:12] 📐 Resize: 1920x1080 @ 1.12s
[post_informer] [2026-01-05 06:01:12] 🎬 Video: 1800s @ 13.21s
```

---

## Troubleshooting

- **No API key configured** → Set `openai_api_key` in add-on configuration
- **Prompt generation fails** → Check `prompt_model` is valid and API key has access
- **Image generation fails** → Verify `image_model` is correct and accessible
- **Search prompts show as "(none)"** → Check add-on logs for SEARCH_PROMPTS env var value. Ensure yaml list format is correct.
- **Files not appearing** → Verify `output_dir` is accessible. `/media` folder is recommended.
- **Entity gathering fails** → Ensure entity IDs exist in Home Assistant

---

## Advanced Topics

For technical details, development info, and advanced customization, see [DEVELOPERS.md](DEVELOPERS.md).

---

## Support

- **Issues**: https://github.com/mythosaz/ha-addons/issues
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

## License

MIT
