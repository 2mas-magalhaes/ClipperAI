# ClipAI

AI-assisted video automation system for turning long-form YouTube videos into short-form clips.

ClipAI combines video download, local speech transcription, LLM-based clip selection, automated editing, a web processing queue, and YouTube publishing through OAuth.

## ✨ Highlights

- End-to-end pipeline from YouTube video to edited short-form clips
- Local transcription with Faster-Whisper
- Local LLM analysis through Ollama
- Automated vertical video editing with subtitles and visual effects
- Web interface for queue, review, publishing, channels, and settings
- Background worker for automated processing
- Real YouTube publishing through OAuth-authenticated uploads
- Manual review fallback when automatic publishing fails

## Overview

ClipAI automates the workflow of processing a source video into ready-to-publish short-form clips.

```text
YouTube video
    -> Download
    -> Audio extraction
    -> Transcription
    -> LLM analysis
    -> Clip selection
    -> Automated editing
    -> Review queue
    -> YouTube publishing
```

The system can be used through the web application or through the direct script pipeline.

## 🚀 Core Features

### Video Processing

- YouTube video download using `yt-dlp`
- Audio extraction from downloaded videos
- Local speech transcription using Faster-Whisper
- GPU-aware execution when CUDA is available

### AI Analysis

- Transcript analysis using a local LLM through Ollama
- Configurable Ollama model support
- Automatic identification of candidate clip segments
- Metadata generation for clips and publishing workflows

### Automated Editing

- Precise clip cutting with FFmpeg
- Vertical 9:16 formatting for short-form platforms
- Word-by-word ASS subtitles
- Jump cuts based on speech intervals
- Face-aware crop and tracking using OpenCV DNN with fallback support
- Dynamic zoom, color grading, denoise, sharpening, vignette, progress bar, and loop handling

### Web Workflow

- Queue-based video processing
- Background worker execution
- Review workflow for generated clips
- Channel and publishing configuration
- Manual and automatic publishing modes
- Upload logs and status tracking

### YouTube Publishing

- Real YouTube uploads through OAuth
- Channel-specific credentials
- Credential fallback/rotation support
- Title, description, tags, category, and privacy configuration
- Scheduled publishing support
- Resumable uploads with progress logging
- Database updates with YouTube video ID and URL

## 🏗️ Architecture

```text
                         +-------------------+
                         |   Web Interface   |
                         |      app.py       |
                         +---------+---------+
                                   |
                                   v
+-------------+          +---------+---------+          +----------------+
| YouTube URL |--------->|   Queue Worker    |--------->| Review/Publish |
+-------------+          |     worker.py     |          +----------------+
                         +---------+---------+
                                   |
        +--------------------------+--------------------------+
        |                          |                          |
        v                          v                          v
+---------------+        +-------------------+        +----------------+
| Download      |        | Analysis          |        | Editing        |
| modulo1       |        | modulo2           |        | modulo3        |
+---------------+        +-------------------+        +----------------+
        |                          |                          |
        v                          v                          v
 yt-dlp download          Whisper + Ollama             FFmpeg pipeline
```

## Main Components

| Component | File | Responsibility |
| --- | --- | --- |
| Download module | `modulo1_download.py` | Downloads source videos from YouTube using `yt-dlp`. |
| Analysis module | `modulo2_analise.py` | Extracts audio, transcribes speech, analyzes transcripts with Ollama, and saves clip recommendations. |
| Editing module | `modulo3_edicao.py` | Generates edited short-form clips with subtitles, vertical formatting, face-aware crop, and visual effects. |
| Web application | `app.py` | Provides the interface for queue management, review, publishing, channels, OAuth, and settings. |
| Queue worker | `worker.py` | Processes videos in the background and coordinates download, analysis, editing, and publishing. |
| Database layer | `database.py` | Stores queue state, clip metadata, channel configuration, settings, publishing status, and YouTube results. |

## Processing Flow

```text
queued
  -> downloading
  -> analyzing
  -> editing
  -> review or publishing
  -> published
```

If automatic publishing is enabled and a valid channel/OAuth configuration exists, edited clips are uploaded directly to YouTube. If publishing fails, the clip remains available for manual review and retry.

## 🧠 AI Workflow

ClipAI uses AI in two main stages:

1. **Transcription:** Faster-Whisper converts the video audio into timestamped text.
2. **Clip analysis:** A local Ollama model analyzes the transcript and recommends short-form clip candidates.

The goal is to keep the analysis workflow local, configurable, and independent from paid API requirements.

## YouTube Publishing

ClipAI supports real YouTube uploads through OAuth-authenticated publishing.

The publishing workflow includes:

- channel-specific OAuth credentials
- upload credential fallback/rotation
- video metadata generation
- title, description, tags, category, and privacy settings
- scheduled publishing support
- resumable uploads with progress logging
- database update with YouTube video ID and URL
- fallback to manual review on upload failure

Additional implementation notes are documented in `AUTO_PUBLISH_LOGS.md`.

## Technologies

| Area | Technology |
| --- | --- |
| Language | Python |
| Video download | yt-dlp |
| Transcription | Faster-Whisper |
| LLM analysis | Ollama with compatible local models |
| Video processing | FFmpeg |
| Image and face processing | OpenCV, PIL |
| GPU support | PyTorch, CUDA where available |
| Web application | Python web application |
| Publishing | YouTube Data API, OAuth |
| Storage | Local database layer |

## Requirements

- Python 3.9 or later
- FFmpeg installed and available in the system path
- Ollama installed locally
- A compatible Ollama model, such as Llama 3.1 or another configured model
- Faster-Whisper dependencies
- YouTube API OAuth credentials for publishing features
- Optional NVIDIA GPU with CUDA for faster transcription and processing

## Installation

Clone the repository:

```bash
git clone https://github.com/2mas-magalhaes/ClipperAI.git
cd ClipperAI
```

Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows:

```powershell
.\venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Install and configure Ollama:

```bash
ollama pull llama3.1
```

## Running the Application

Run the web application:

```powershell
$env:PYTHONIOENCODING = "utf-8"; .\venv\Scripts\python.exe app.py
```

Run the direct script pipeline:

```bash
python main.py
```

Run GPU diagnostics:

```bash
python verificar_gpu.py
```

## Configuration

For YouTube publishing, configure a channel through the web interface and provide OAuth credentials for the YouTube Data API.

Recommended workflow:

1. Add a channel in the web interface.
2. Configure OAuth credentials for that channel.
3. Enable automatic publishing globally or per queue item.
4. Start the worker.
5. Add videos to the queue.

If credentials are missing or upload fails, clips remain available for review and manual publishing.

## Example Programmatic Usage

```python
from modulo1_download import baixar_video_youtube
from modulo2_analise import (
    extrair_audio_do_video,
    transcrever_audio_whisper,
    analisar_com_ollama,
)

url = "https://www.youtube.com/watch?v=example"
video_path = baixar_video_youtube(url, "input_video")
audio_path = extrair_audio_do_video(video_path)
transcript = transcrever_audio_whisper(audio_path)
clip_candidates = analisar_com_ollama(transcript)
```

## Project Status

Implemented:

- YouTube video download
- audio extraction
- local transcription
- local LLM-based clip analysis
- automatic clip editing
- vertical video export
- dynamic subtitles
- web interface
- processing queue
- background worker
- manual review workflow
- real YouTube upload through OAuth
- automatic publishing workflow
- upload logging and database updates

Planned or expandable:

- support for additional local LLM models
- advanced scheduling controls
- analytics dashboard
- additional publishing targets

## Responsible Use

ClipAI is intended for lawful and responsible content workflows. Users should respect copyright, platform terms of service, and the rights of original creators. Automated editing and publishing features should be used only with content the user owns, has permission to use, or can lawfully transform and publish.

## License

MIT License. See `LICENSE.md` for details.
