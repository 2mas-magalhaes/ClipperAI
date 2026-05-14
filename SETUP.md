# ClipperAI Setup Guide

## Prerequisites Checklist

- [ ] Python 3.9 or later installed (`python --version`)
- [ ] pip package manager working (`pip --version`)
- [ ] Git installed (`git --version`)
- [ ] FFmpeg installed and in PATH (`ffmpeg -version`)
- [ ] At least 4GB RAM available
- [ ] Internet connection for initial downloads

### Optional but Recommended

- [ ] NVIDIA GPU with CUDA support (`nvidia-smi`)
- [ ] 8GB+ RAM if using GPU

---

## Step 1: Install FFmpeg

### Windows

1. Download from https://ffmpeg.org/download.html (Windows builds)
2. Extract to a folder (e.g., `C:\ffmpeg`)
3. Add to PATH:
   - Open System Properties → Environment Variables
   - Add `C:\ffmpeg\bin` to your PATH
   - Restart terminal and verify: `ffmpeg -version`

### macOS

```bash
brew install ffmpeg
ffmpeg -version
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get install ffmpeg
ffmpeg -version
```

---

## Step 2: Install Ollama

1. Go to https://ollama.ai
2. Download the installer for your OS
3. Run the installer
4. Verify installation:

```bash
ollama --version
```

5. Pull the Llama 2 model:

```bash
ollama pull llama2
```

This may take 5-10 minutes depending on internet speed. The model is ~4GB.

6. Verify the model is available:

```bash
ollama list
```

You should see `llama2` in the list.

---

## Step 3: Clone and Setup ClipperAI

```bash
git clone https://github.com/2mas-magalhaes/ClipperAI.git
cd ClipperAI
```

Create a Python virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment:

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Step 4: Configure Environment (Optional)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Set to false if you don't have a GPU
USE_GPU=true

# Model settings (change to your preferred model)
OLLAMA_MODEL=llama2
WHISPER_MODEL=base
```

---

## Step 5: Verify GPU Support (Optional)

Run the GPU verification script:

```bash
python verificar_gpu.py
```

**Output:**
- If GPU is available, you'll see NVIDIA GPU info and CUDA version
- If no GPU, it will show CPU fallback is active

GPU is optional. The pipeline will work on CPU, just slower.

---

## Step 6: Run ClipperAI

Ensure Ollama is running in another terminal:

```bash
ollama serve
```

Then run the main pipeline:

```bash
python main.py
```

---

## Project Structure

```
ClipperAI/
├── README.md
├── SETUP.md
├── requirements.txt
├── .env.example
├── .env (your local config)
├── main.py
├── modulo1_download.py
├── modulo2_analise.py
├── modulo3_edicao.py
├── modulo4_publicacao.py (planned)
├── modulo5_feedback.py (planned)
├── verificar_gpu.py
├── downloads/
├── audio/
├── video/
└── output/
```

---

## Common Issues

### Issue: "ffmpeg not found"

**Solution:**
- Verify FFmpeg is installed: `ffmpeg -version`
- Make sure FFmpeg is in your system PATH
- On Windows, restart your terminal after adding to PATH

### Issue: "ollama pull llama2" fails

**Solution:**
- Make sure Ollama is installed: `ollama --version`
- Check internet connection
- Try again: `ollama pull llama2`
- If still fails, try a smaller model first: `ollama pull mistral`

### Issue: "CUDA not found" or GPU not detected

**Solution:**
- GPU is optional. CPU fallback is automatic.
- To use GPU, ensure you have:
  - NVIDIA GPU (RTX/GTX series)
  - CUDA Toolkit installed
  - cuDNN installed
- Run `nvidia-smi` to check GPU
- If not available, set `USE_GPU=false` in .env

### Issue: "Out of memory" or "CUDA out of memory"

**Solution:**
- Reduce model size: Use `whisper.tiny` or `whisper.small` instead of `base`
- Reduce video resolution
- Close other applications
- If using GPU, reduce batch size in configuration

### Issue: "Python module not found"

**Solution:**
- Make sure virtual environment is activated
- Verify requirements are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.9+)

---

## Performance Tips

### For Faster Transcription

1. Use GPU if available: `USE_GPU=true`
2. Use smaller Whisper model: `WHISPER_MODEL=tiny` or `WHISPER_MODEL=small`
3. Lower sample rate if acceptable

### For Faster LLM Analysis

1. Use smaller model: `ollama pull mistral` (faster than llama2)
2. Set shorter timeout: `OLLAMA_TIMEOUT=120`

### For Faster Overall Pipeline

1. Download video at lower resolution
2. Use GPU acceleration
3. Run on a machine with at least 8GB RAM

---

## Next Steps

1. Run your first video analysis
2. Check the output in `output/`
3. Review identified clip timestamps
4. Experiment with different models and settings
5. Read the main README.md for architecture details

---

## Troubleshooting

For additional help:

1. Check the main README.md for project architecture
2. Review the module docstrings in Python files
3. Check Ollama documentation: https://ollama.ai
4. Check Faster-Whisper documentation: https://github.com/SYSTRAN/faster-whisper
