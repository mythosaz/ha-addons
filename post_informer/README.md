# Post Informer Add-on

AI-powered HUD display generator for Home Assistant - gathers context, generates images, creates videos.

## About

Post Informer is a complete pipeline that transforms your Home Assistant data into stunning visual displays. It gathers entity states, uses AI to create contextual "vibe-based" prompts, generates high-quality images, and optionally converts them to looping videos for smart displays.

### The Pipeline

1. **Gather Context** - Collects state data from your configured HA entities (sensors, calendars, todo lists, etc.)
2. **Discover Location** - Automatically detects timezone and location from zone.home for local news
3. **Generate Art Prompt** - Sends context to gpt-5.2 with web search enabled for current news integration
4. **Render Image** - Uses gpt-image-1.5 to generate a high-resolution image (1536×1024)
5. **Resize** - Scales the image to your target display resolution (4K, 1080p, 720p, 480p)
6. **Create Video** - Converts the image to a looping video for continuous display
7. **Fire Events** - Notifies Home Assistant when each step completes

### Features

- **Web Search Integration**: AI searches current news (national + local) during prompt generation
- **Location Auto-Discovery**: Automatically detects your timezone and location from Home Assistant
- **Jinja2 Template Support**: Use templates in entity_ids for dynamic data extraction
- **No timeout limits**: Runs as persistent service (bypasses shell_command timeouts)
- **Fully automated pipeline**: One command triggers the entire workflow
- **Highly configurable**: Customize prompts, models, resolutions, video settings
- **Comprehensive logging**: Detailed timing metrics for every step
- **Event-driven**: Fires HA events for image complete, video complete, and pipeline complete
- **Flexible entity selection**: Monitor any HA entities (weather, calendars, sensors, etc.)
- **Multiple output formats**: Original high-res + resized images + video
- **UTF-8 Support**: Properly handles special characters (°, etc.)

## Installation

1. Add this repository to your Home Assistant:
   - Settings → Add-ons → Add-on Store → ⋮ → Repositories
   - Add: `https://github.com/mythosaz/ha-addons`

2. Install the "Post Informer" add-on

3. Configure the add-on (see Configuration section below)

4. Start the add-on

## Configuration

### Minimal Configuration

```yaml
openai_api_key: "sk-your-api-key-here"
entity_ids: |
  sensor.weather_temperature
  calendar.family
  todo.shopping_list
```

### Full Configuration Example

```yaml
# API Configuration
openai_api_key: "sk-your-api-key-here"
prompt_model: "gpt-5.2"
image_model: "gpt-image-1.5"

# Entity Monitoring
entity_ids: |
  sensor.weather_temperature
  sensor.weather_condition
  calendar.family
  calendar.work
  todo.shopping_list
  sensor.living_room_temperature
  light.kitchen
  binary_sensor.front_door

# Prompt Customization
use_default_prompts: true
custom_system_prompt: ""
custom_user_prompt: ""

# Image Configuration
image_quality: "high"
image_size: "1536x1024"

# Resize Configuration
resize_output: true
target_resolution: "1080p"  # Options: 4k, 1080p, 720p, 480p, or custom like "1920x1080"
save_original: true

# Video Configuration
enable_video: true
video_duration: 1800  # 30 minutes (in seconds)
video_framerate: "0.25"  # 1 frame every 4 seconds
use_default_ffmpeg: true
custom_ffmpeg_args: ""

# Output
output_dir: "/media/post_informer"
filename_prefix: "post_informer"
```

### Configuration Options

#### API Configuration

- **openai_api_key** (required): Your OpenAI API key
- **prompt_model** (default: `gpt-5.2`): Model for generating art prompts with web search
- **image_model** (default: `gpt-image-1.5`): Model for rendering images

#### Entity Monitoring

- **entity_ids**: List of HA entity IDs or Jinja2 templates to monitor
  - Supports multiple formats:
    - **Plain entity IDs**: `sensor.temperature`, `calendar.events`, `todo.tasks`
    - **Jinja2 templates**: `{{ states('lock.front_door') }}`, `{{ state_attr('sensor.weather', 'temperature') }}`
    - **Newline-separated** (recommended): Use `|` or `|-` for literal newlines
    - **Space-separated**: Use `>-` (YAML folded scalar)
    - **Comma-separated**: `sensor.a, sensor.b, sensor.c`
  - Mix and match plain IDs and templates as needed
  - Leave blank to skip entity gathering (you can still trigger with custom prompts)

**Format Examples:**
```yaml
# Plain entity IDs (recommended for full entity data)
entity_ids: |
  sensor.weather_temperature
  calendar.family
  todo.shopping_list

# With Jinja2 templates (for specific values)
entity_ids: |
  sensor.weather_temperature
  lock.front_door
  {{ states('lock.front_door') }}
  Battery: {{ state_attr('lock.front_door', 'battery_level') }}%

# Space-separated (YAML folded scalar)
entity_ids: >-
  sensor.weather_temperature
  calendar.family
  todo.shopping_list

# Comma-separated
entity_ids: "sensor.weather_temperature, calendar.family, todo.shopping_list"
```

#### Prompt Customization

- **use_default_prompts** (default: `true`): Use built-in HUD-style prompts
- **custom_system_prompt**: Your custom system prompt (when `use_default_prompts: false`)
- **custom_user_prompt**: Your custom user prompt template (use `{context}` placeholder)

#### Image Configuration

- **image_quality** (default: `high`): OpenAI image quality (`low`, `medium`, `high`, `auto`)
- **image_size** (default: `1536x1024`): Image dimensions

#### Resize Configuration

- **resize_output** (default: `true`): Enable image resizing
- **target_resolution** (default: `1080p`): Target resolution
  - Presets: `4k` (3840×2560), `1080p` (1920×1280), `720p` (1280×854), `480p` (640×427)
  - Custom: `1920x1080` format
- **save_original** (default: `true`): Keep original high-res image

#### Video Configuration

- **enable_video** (default: `true`): Create video from image
- **video_duration** (default: `1800`): Video length in seconds
- **video_framerate** (default: `0.25`): Framerate (fractional supported)
- **use_default_ffmpeg** (default: `true`): Use built-in ffmpeg settings
- **custom_ffmpeg_args**: Custom ffmpeg arguments (advanced users)

#### Output

- **output_dir** (default: `/media/post_informer`): Where to save files
- **filename_prefix** (default: `post_informer`): Prefix for generated filenames

## Usage

### Triggering via Automation

```yaml
service: hassio.addon_stdin
data:
  addon: ADDON_SLUG_post_informer
  input:
    action: "generate"
```

### Scheduled Generation

```yaml
automation:
  - alias: "Generate Morning HUD Display"
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

### Listening for Completion Events

The add-on fires three types of events:

#### 1. Image Complete Event

```yaml
automation:
  - alias: "HUD Image Ready"
    trigger:
      - platform: event
        event_type: post_informer_image_complete
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.success }}"
    action:
      - service: notify.mobile_app
        data:
          message: "HUD image generated!"
```

Event data:
```json
{
  "success": true,
  "image": "/media/post_informer/post_informer.png",
  "archive": "/media/post_informer/archive/post_informer_202601050600.png",
  "resolution": "1080p",
  "timestamp": "2026-01-05T06:00:00"
}
```

#### 2. Video Complete Event

```yaml
automation:
  - alias: "Play HUD Video on Living Room TV"
    trigger:
      - platform: event
        event_type: post_informer_video_complete
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.success }}"
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.living_room_tv
        data:
          media_content_id: "{{ trigger.event.data.video }}"
          media_content_type: "video/mp4"
```

Event data:
```json
{
  "success": true,
  "video": "/media/post_informer/post_informer.mp4",
  "duration": 1800,
  "timestamp": "2026-01-05T06:00:00"
}
```

#### 3. Pipeline Complete Event

```yaml
automation:
  - alias: "Log Pipeline Completion"
    trigger:
      - platform: event
        event_type: post_informer_complete
    action:
      - service: logbook.log
        data:
          name: "Post Informer"
          message: "Pipeline completed in {{ trigger.event.data.total_time }}s"
```

Event data includes full pipeline details:
```json
{
  "success": true,
  "timestamp": "2026-01-05T06:00:00",
  "image": "/media/post_informer/post_informer.png",
  "archive": "/media/post_informer/archive/post_informer_202601050600.png",
  "video": "/media/post_informer/post_informer.mp4",
  "total_time": 67.42,
  "steps": {
    "gather_entities": {...},
    "generate_prompt": {...},
    "generate_image": {...},
    "resize_image": {...},
    "create_video": {...}
  }
}
```

## File Outputs

Each pipeline run generates or overwrites working files, with optional archiving:

```
/media/post_informer/
  post_informer.png                        # Working image (resized, always overwritten)
  post_informer.mp4                        # Working video (if enabled, always overwritten)

  archive/                                 # Archive directory (only if save_original enabled)
    post_informer_202601050600.png         # Original high-res with embedded metadata
    post_informer_202601051200.png         # Next generation...
    ...
```

**Working files**: The `post_informer.png` and `post_informer.mp4` files are always overwritten with the latest generation, making them easy to reference in automations and displays.

**Archive**: When `save_original` is enabled, the original high-resolution image is saved to the `archive/` subdirectory with a timestamp and embedded metadata (prompt, model, etc.). This preserves a complete history of generations. The metadata is embedded using ImageMagick and can be viewed with tools like `exiftool` or `identify -verbose`.

## Default Prompts

The add-on includes sophisticated default prompts that:
- Synthesize a "vibe" from your HA data
- Create futuristic HUD-style displays
- Incorporate contextual information (weather, calendar, tasks)
- Search for news headlines (national + local Phoenix)
- Use creative visual styles (vaporwave, cyberpunk, Art Deco, etc.)
- Optimize for QLED display dynamic range

You can use the defaults or provide your own custom prompts.

## Logs

View comprehensive logging in the add-on logs:

```
[post_informer] [2026-01-05 06:00:00] Add-on started, waiting for input...
[post_informer] [2026-01-05 06:00:00] Config: gpt-4o → gpt-image-1.5
[post_informer] [2026-01-05 06:00:05] ============================================================
[post_informer] [2026-01-05 06:00:05] STARTING PIPELINE
[post_informer] [2026-01-05 06:00:05] ============================================================
[post_informer] [2026-01-05 06:00:05] Gathering 8 entity states...
[post_informer] [2026-01-05 06:00:06] Gathered 8 entities (0.82s)
[post_informer] [2026-01-05 06:00:06] Generating art prompt with gpt-4o...
[post_informer] [2026-01-05 06:00:06] Context size: 3421 chars
[post_informer] [2026-01-05 06:00:15] Generated prompt (2847 chars) (8.94s)
[post_informer] [2026-01-05 06:00:15] Prompt preview: Create a kinetic vaporwave cityscape...
[post_informer] [2026-01-05 06:00:15] Rendering image with gpt-image-1.5...
[post_informer] [2026-01-05 06:00:15] Quality: high, Size: 1536x1024
[post_informer] [2026-01-05 06:00:58] Image rendered: /media/post_informer/post_informer_temp.png (42.31s)
[post_informer] [2026-01-05 06:00:58] Archiving original to /media/post_informer/archive/post_informer_202601050600.png
[post_informer] [2026-01-05 06:00:58] Embedded metadata into /media/post_informer/archive/post_informer_202601050600.png
[post_informer] [2026-01-05 06:00:58] Resizing to 1920x1080...
[post_informer] [2026-01-05 06:00:59] Image resized: /media/post_informer/post_informer.png (1.12s)
[post_informer] [2026-01-05 06:00:59] Generated working image: /media/post_informer/post_informer.png
[post_informer] [2026-01-05 06:00:59] Fired event post_informer_image_complete: HTTP 200
[post_informer] [2026-01-05 06:00:59] Creating video (1800s @ 0.25 fps)...
[post_informer] [2026-01-05 06:01:12] Video created: /media/post_informer/post_informer.mp4 (13.21s)
[post_informer] [2026-01-05 06:01:12] Generated video: /media/post_informer/post_informer.mp4
[post_informer] [2026-01-05 06:01:12] Fired event post_informer_video_complete: HTTP 200
[post_informer] [2026-01-05 06:01:12] ============================================================
[post_informer] [2026-01-05 06:01:12] PIPELINE COMPLETE (67.42s)
[post_informer] [2026-01-05 06:01:12] ============================================================
[post_informer] [2026-01-05 06:01:12] SUCCESS: Generated /media/post_informer/post_informer.png
[post_informer] [2026-01-05 06:01:12] SUCCESS: Archived to /media/post_informer/archive/post_informer_202601050600.png
[post_informer] [2026-01-05 06:01:12] SUCCESS: Generated /media/post_informer/post_informer.mp4
```

## Example Use Cases

### Morning Smart Mirror Display

Generate a fresh HUD display every morning with weather, calendar, and tasks:

```yaml
automation:
  - alias: "Generate Morning Display"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: hassio.addon_stdin
        data:
          addon: ADDON_SLUG_post_informer
          input:
            action: "generate"

  - alias: "Show on Bedroom Display"
    trigger:
      - platform: event
        event_type: post_informer_video_complete
    action:
      - service: media_player.play_media
        target:
          entity_id: media_player.bedroom_display
        data:
          media_content_id: "{{ trigger.event.data.video }}"
          media_content_type: "video/mp4"
```

### Rotating Kitchen Display

Update every 4 hours with fresh context:

```yaml
automation:
  - alias: "Update Kitchen Display"
    trigger:
      - platform: time_pattern
        hours: "/4"  # Every 4 hours
    action:
      - service: hassio.addon_stdin
        data:
          addon: ADDON_SLUG_post_informer
          input:
            action: "generate"
```

### Event-Triggered Updates

Generate new displays when important events occur:

```yaml
automation:
  - alias: "Update Display on Calendar Changes"
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

## Troubleshooting

### No API key configured
Ensure you've set `openai_api_key` in the add-on configuration.

### Pipeline fails at prompt generation
Check that `prompt_model` (default: `gpt-4o`) is valid and your API key has access.

### Pipeline fails at image generation
Verify `image_model` (default: `gpt-image-1.5`) is correct and accessible.

### Video encoding fails
Check that `video_framerate` and `video_duration` are valid values.

### Files not appearing
Verify `output_dir` is accessible. The `/media` folder is recommended as it's shared with HA.

### Entity gathering fails
Ensure entity IDs are valid and exist in your HA instance.

## Supported Architectures

- aarch64 (ARM 64-bit)
- amd64 (x86 64-bit)

## Performance Notes

- **Prompt generation**: ~5-15 seconds (depends on context size and GPT-4o response time)
- **Image rendering**: ~30-60 seconds (depends on gpt-image-1.5 load)
- **Resize**: <2 seconds
- **Video encoding**: ~10-20 seconds (for 30-minute video with ultrafast preset)
- **Total pipeline**: ~60-90 seconds end-to-end

## License

MIT

## Support

Report issues at: https://github.com/mythosaz/ha-addons/issues
