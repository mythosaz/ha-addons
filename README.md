# Home Assistant Custom Addons

Custom Home Assistant addons for extended functionality.

## Installation

1. In Home Assistant, navigate to **Settings** → **Add-ons** → **Add-on Store**
2. Click the **⋮** menu (top right) → **Repositories**
3. Add this repository URL: `https://github.com/mythosas/ha-addons`
4. The addons will appear in your add-on store

## Available Addons

### OpenAI Image Generator

Long-running OpenAI image generation service that bypasses Home Assistant's shell_command timeout limits.

- Generates images via OpenAI API (DALL-E or GPT-image models)
- Reads commands from stdin, runs indefinitely
- Automatic versioning: saves both timestamped archives and current versions
- Fires Home Assistant events on completion

[View addon documentation](openai_image/README.md)

## Support

For issues or feature requests, please use the [GitHub issue tracker](https://github.com/mythosas/ha-addons/issues).
