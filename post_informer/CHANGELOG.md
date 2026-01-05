# Changelog

All notable changes to this add-on will be documented in this file.

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
