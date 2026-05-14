# ClipAI

ClipAI is an AI-assisted video automation system for processing long-form YouTube videos into short-form clips. It combines video download, local speech transcription, LLM-based clip selection, automated editing, a web-based processing queue, and YouTube publishing through OAuth.

The project is designed as an end-to-end pipeline for experimenting with AI-assisted content workflows while keeping the core processing local and configurable.

## Overview

ClipAI automates the workflow of turning a source video into edited short-form clips:

1. Download a YouTube video.
2. Extract and transcribe the audio locally.
3. Analyze the transcript with a local LLM through Ollama.
4. Select candidate segments for short-form clips.
5. Edit the clips automatically with subtitles, vertical formatting, visual effects, and optional Clippy-generated hooks.
6. Manage clips through a web interface and processing queue.
7. Publish clips to YouTube using OAuth-authenticated uploads.

## Current Capabilities

- YouTube video download using `yt-dlp`
- Local transcription with Faster-Whisper
- Local LLM analysis through Ollama
- Automated clip selection based on transcript analysis
- Automated video editing with FFmpeg-based processing
- Vertical 9:16 clip formatting
- Word-by-word ASS subtitles
- Jump cuts based on speech intervals
- Face-aware crop and tracking using OpenCV DNN with fallback support
- Dynamic zoom, color grading, denoise, sharpening, vignette, progress bar, and loop handling
- Optional Clippy character layer for AI-generated hook segments
- Web interface for queue, review, publishing, channels, and settings
- Background worker for automated processing
- Real YouTube publishing through OAuth
- Upload progress logging and database updates with YouTube video URL and ID
- Manual review fallback when automatic publishing fails

## Architecture

```text
YouTube URL
    |
    v
Download module
    |
    v
Audio extraction
    |
    v
Faster-Whisper transcription
    |
    v
Ollama LLM analysis
    |
    v
Clip candidate selection
    |
    v
FFmpeg editing pipeline
    |
    v
Review queue / Web interface
    |
    v
YouTube OAuth publishing
Main Components
Download Module

File: modulo1_download.py

Responsible for downloading source videos from YouTube using yt-dlp and storing them locally for processing.

Analysis Module

File: modulo2_analise.py

Handles audio extraction, transcription with Faster-Whisper, local LLM analysis through Ollama, GPU detection, and saving the resulting clip recommendations.

Editing Module

File: modulo3_edicao.py

Generates edited short-form clips from the recommended timestamps. The editing pipeline includes precise video cuts, jump cuts, subtitle generation, vertical formatting, face-aware cropping, visual effects, and export encoding.

Clippy Character Module

File: personagem_clippy.py

Generates and animates an optional AI character layer used for hook-style introductions and visual interventions.

Web Application

File: app.py

Provides the web interface for queue management, review, publishing, channel configuration, OAuth authentication, settings, and manual publishing workflows.

Queue Worker

File: worker.py

Processes videos in the background. The worker handles download, transcription, LLM analysis, editing, review creation, automatic publishing, retry behavior, and detailed logging.

Database Layer

File: database.py

Stores queue state, clip metadata, review status, published videos, channel configuration, settings, and YouTube publishing results.

Processing Flow
queued
  -> downloading
  -> analyzing
  -> editing
  -> review or publishing
  -> published

If automatic publishing is enabled and a valid channel/OAuth configuration exists, edited clips are uploaded directly to YouTube. If publishing fails, the clip remains available for manual review and retry.

YouTube Publishing

ClipAI supports real YouTube uploads through OAuth-authenticated publishing. The publishing workflow includes:

channel-specific OAuth credentials
upload credential fallback/rotation
video metadata generation
title, description, tags, category, and privacy settings
scheduled publishing support
resumable uploads with progress logging
database update with YouTube video ID and URL
fallback to manual review on upload failure

Additional implementation notes are documented in AUTO_PUBLISH_LOGS.md.

Technologies
Area	Technology
Language	Python
Video download	yt-dlp
Transcription	Faster-Whisper
LLM analysis	Ollama with compatible local models
Video processing	FFmpeg
Image and face processing	OpenCV, PIL
GPU support	PyTorch, CUDA where available
Web application	Python web application
Publishing	YouTube Data API, OAuth
Storage	Local database layer
Requirements
Python 3.9 or later
FFmpeg installed and available in the system path
Ollama installed locally
A compatible Ollama model, such as Llama 3.1 or another configured model
Faster-Whisper dependencies
YouTube API OAuth credentials for publishing features
Optional NVIDIA GPU with CUDA for faster transcription and processing
Installation

Clone the repository:

git clone https://github.com/2mas-magalhaes/ClipperAI.git
cd ClipperAI

Create and activate a virtual environment:

python -m venv venv

Windows:

.\venv\Scripts\activate

macOS/Linux:

source venv/bin/activate

Install dependencies:

pip install -r requirements.txt

Install and configure Ollama:

ollama pull llama3.1
Running the Application

Run the web application:

$env:PYTHONIOENCODING = "utf-8"; .\venv\Scripts\python.exe app.py

Or run the direct script pipeline:

python main.py

GPU diagnostics:

python verificar_gpu.py
Configuration

For YouTube publishing, configure a channel through the web interface and provide OAuth credentials for the YouTube Data API.

Expected workflow:

Add a channel in the web interface.
Configure OAuth credentials for that channel.
Enable automatic publishing in settings or per queue item.
Start the worker.
Add videos to the queue.

If credentials are missing or upload fails, clips are kept available for review and manual publishing.

Example Programmatic Usage
from modulo1_download import baixar_video_youtube
from modulo2_analise import extrair_audio_do_video, transcrever_audio_whisper, analisar_com_ollama

url = "https://www.youtube.com/watch?v=example"
video_path = baixar_video_youtube(url, "input_video")
audio_path = extrair_audio_do_video(video_path)
transcript = transcrever_audio_whisper(audio_path)
clip_candidates = analisar_com_ollama(transcript)
Project Status

Implemented:

YouTube video download
audio extraction
local transcription
local LLM-based clip analysis
automatic clip editing
vertical video export
dynamic subtitles
Clippy character layer
web interface
processing queue
background worker
manual review workflow
real YouTube upload through OAuth
automatic publishing workflow
upload logging and database updates

Planned or expandable:

support for additional local LLM models
advanced scheduling controls
analytics dashboard
additional publishing targets
Notes on Responsible Use

This project is intended for lawful and responsible content workflows. Users should respect copyright, platform terms of service, and the rights of original creators. Automated editing and publishing features should be used only with content the user owns, has permission to use, or can lawfully transform and publish.

License

MIT License. See LICENSE.md for details.
