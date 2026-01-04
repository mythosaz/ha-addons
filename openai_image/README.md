# OpenAI Image Generator Add-on

Long-running OpenAI image generation service for Home Assistant that bypasses shell_command timeout limits.

## About

This add-on provides a persistent service that generates images using OpenAI's API (DALL-E or GPT-image models). Unlike Home Assistant's built-in `shell_command`, this add-on runs continuously and accepts commands via stdin, eliminating timeout issues for long-running image generation tasks.

### Features

- **No timeout limits**: Runs as a persistent service
- **Multiple OpenAI models**: Supports DALL-E and GPT-image models
- **Automatic versioning**: Saves both timestamped archives and current versions
- **Event-driven**: Fires Home Assistant events when generation completes
- **Flexible input**: Accepts prompts directly or from files
- **Configurable defaults**: Set default model, quality, size, and output directory

## Installation

1. Add this repository to your Home Assistant:
   - Settings → Add-ons → Add-on Store → ⋮ → Repositories
   - Add: `https://github.com/YOURUSERNAME/ha-addons`

2. Install the "OpenAI Image Generator" add-on

3. Configure the add-on (see Configuration section below)

4. Start the add-on

## Configuration

### Add-on Options

```yaml
openai_api_key: "sk-your-api-key-here"
default_model: "gpt-image-1"
default_quality: "high"
default_size: "1536x1024"
output_dir: "/media/generated"
```

#### Option Details

- **openai_api_key** (required): Your OpenAI API key
- **default_model** (optional): Default model to use (`gpt-image-1` or DALL-E models)
- **default_quality** (optional): Image quality (`low`, `medium`, `high`, or `auto`)
- **default_size** (optional): Image dimensions (`1024x1024`, `1536x1024`, `1024x1536`, or `auto`)
- **output_dir** (optional): Directory to save generated images (default: `/media/generated`)

## Usage

### Using stdin_command in Automations

The add-on reads JSON commands from stdin. Use Home Assistant's `stdin` service:

```yaml
service: hassio.addon_stdin
data:
  addon: ADDON_SLUG_openai_image
  input:
    prompt: "A serene mountain landscape at sunset"
    filename: "morning_postcard.png"
    model: "gpt-image-1"
    quality: "high"
    size: "1536x1024"
```

### Input Fields

- **prompt** (required if no prompt_file): The image generation prompt
- **prompt_file** (optional): Path to a file containing the prompt (e.g., `/config/prompt.txt`)
- **filename** (optional): Output filename (auto-generated if not specified)
- **model** (optional): Override default model
- **quality** (optional): Override default quality
- **size** (optional): Override default size

### Example Automation

```yaml
automation:
  - alias: "Generate Morning Postcard"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: hassio.addon_stdin
        data:
          addon: ADDON_SLUG_openai_image
          input:
            prompt_file: "/config/morning_prompt.txt"
            filename: "morning_postcard.png"
            quality: "high"
```

### Listening for Completion Events

The add-on fires an `openai_image_complete` event when generation finishes:

```yaml
automation:
  - alias: "Send Image When Ready"
    trigger:
      - platform: event
        event_type: openai_image_complete
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.success }}"
    action:
      - service: notify.telegram
        data:
          message: "Your image is ready!"
          data:
            photo:
              - file: "{{ trigger.event.data.filepath }}"
```

### Event Data

Success event:
```json
{
  "success": true,
  "filepath": "/media/generated/morning_postcard.png",
  "filepath_archived": "/media/generated/202601040700-morning_postcard.png",
  "filename": "morning_postcard.png",
  "filename_archived": "202601040700-morning_postcard.png",
  "model": "gpt-image-1",
  "size": "1536x1024",
  "render_time_seconds": 12.34,
  "prompt_preview": "A serene mountain landscape..."
}
```

Error event:
```json
{
  "success": false,
  "error": "Error message here",
  "render_time_seconds": 1.23,
  "prompt_preview": "A serene mountain landscape..."
}
```

## File Versioning

The add-on saves two versions of each generated image:

1. **Current version**: `filename.png` (overwrites on each generation)
2. **Archived version**: `YYYYMMDDHHMM-filename.png` (timestamped, never overwritten)

This allows you to:
- Always display the latest image using the same filename
- Keep a history of all generated images with timestamps

## Supported Architectures

- aarch64 (ARM 64-bit)
- amd64 (x86 64-bit)

## Logs

View add-on logs for generation status, errors, and render times:

```
[openai_image] Add-on started, waiting for input...
[openai_image] Generating image: model=gpt-image-1, quality=high, size=1536x1024
[openai_image] Prompt: A serene mountain landscape...
[openai_image] render_time_seconds: 12.34
[openai_image] Archived: /media/generated/202601040700-morning_postcard.png
[openai_image] Current: /media/generated/morning_postcard.png
[openai_image] Fired event openai_image_complete: 200
```

## Troubleshooting

### No API key configured
Make sure you've set your OpenAI API key in the add-on configuration.

### Images not appearing
Check the `output_dir` configuration and ensure the directory is accessible. The `/media` folder is recommended as it's shared with Home Assistant.

### Timeout errors
This add-on specifically avoids timeout issues by running as a persistent service. If you're still experiencing problems, check the add-on logs.

## License

MIT

## Support

Report issues at: https://github.com/YOURUSERNAME/ha-addons/issues
