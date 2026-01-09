# Changelog

All notable changes to this add-on will be documented in this file.

## [1.0.5] - 2026-01-09

### Added
- **Responses API Support**: Full integration with OpenAI Responses API for web search capabilities
- **Web Search Integration**: Model can now search current news (national and local) during prompt generation
- **Location Auto-Discovery**: Automatically detects timezone and location from zone.home entity
- **Jinja2 Template Support**: entity_ids now accepts Jinja2 templates (e.g., `{{ states('lock.front_door') }}`)
- **Intelligent API Fallback**: Automatically falls back to Chat Completions if Responses API unavailable
- **Updated System Prompt**: Completely redesigned creative prompt focusing on ambitious visual scenes

### Changed
- **Default Model**: Changed from gpt-4o to gpt-5.2
- **UTF-8 Encoding**: Added explicit UTF-8 support for special characters (°, etc.)
- **Cleaner Logs**: Removed duplicate prompt display from logs
- **Location-Aware News**: Removed hard-coded "Phoenix" - now uses discovered location
- **API Parameter**: Updated to use max_completion_tokens for gpt-5.2 compatibility

### Fixed
- Fixed Responses API request format (developer role, input structure)
- Fixed character encoding issues (degree symbols, etc.)
- Fixed prompt truncation in logs - now displays full prompt
- Fixed invalid schema syntax that prevented addon from appearing in HA

### Technical
- Added jinja2 library support with graceful fallback
- Schema now accepts entity_ids as string (handles both list and string internally)
- Full timezone support for web search localization
- Proper OpenAI SDK usage (client.responses.create)

## [1.0.1] - 2026-01-07

### Added
- **Master Files**: Automatically creates and updates master symlinks for easy access to latest content
  - `hud_display_master.png` - Always points to latest still image (resized or original)
  - `hud_display_master.mp4` - Always points to latest video
  - Makes it easy to configure displays with static paths that always show current content
  - All timestamped versions are retained for history

### Changed
- Video generation remains optional (controlled by `enable_video` setting)
- All generated files (images and videos) are retained without archiving

## [1.0.0] - 2026-01-05

### Added
- Complete AI-powered HUD display generation pipeline
- **Entity Gathering**: Automatically collects Home Assistant entity states
- **AI Prompt Generation**: Uses GPT-4o to create contextual art prompts from HA data
- **Image Rendering**: Generates high-quality images via GPT-image-1.5
- **Image Resizing**: Automatically scales images to target resolutions (4K, 1080p, 720p, 480p)
- **Video Creation**: Converts images to looping videos using ffmpeg
- **Event System**: Fires three event types:
  - `post_informer_image_complete` - Image ready
  - `post_informer_video_complete` - Video ready
  - `post_informer_complete` - Full pipeline complete
- **Comprehensive Logging**: Detailed timing metrics for every pipeline step
- **Flexible Configuration**:
  - Configurable API models (prompt_model, image_model)
  - Entity ID selection (newline or comma-separated)
  - Custom or default prompts
  - Image quality and size options
  - Resize settings with presets or custom resolutions
  - Video duration and framerate control
  - Custom ffmpeg arguments support
- **Default Prompts**: Sophisticated HUD-style prompts with news integration
- **Multiple Output Formats**: Original high-res + resized images + video files
- **Timestamped Files**: All outputs include timestamps for archival
- stdin-based command interface (bypasses HA shell_command timeout limits)

### Technical
- Added ffmpeg dependency for image resize and video encoding
- Python 3 with OpenAI SDK and requests library
- Supports aarch64 and amd64 architectures
- Uses Home Assistant Supervisor API for entity states and event firing
