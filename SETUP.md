# ClipAI Setup Guide

## Prerequisites Checklist

- [ ] Python 3.9 or later installed (`python --version`)
- [ ] pip package manager working (`pip --version`)
- [ ] Git installed (`git --version`)
- [ ] FFmpeg installed and available in PATH (`ffmpeg -version`)
- [ ] At least 4GB RAM available
- [ ] Internet connection for initial downloads

### Optional but Recommended

- [ ] NVIDIA GPU with CUDA support (`nvidia-smi`)
- [ ] 8GB+ RAM if using GPU

---

## Step 1: Install FFmpeg

### Windows

1. Download from https://ffmpeg.org/download.html
2. Extract to a folder such as `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your PATH
4. Restart your terminal and verify with `ffmpeg -version`

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
2. Install Ollama for your OS
3. Verify installation:

```bash
ollama --version
```

4. Pull a local model:

```bash
ollama pull llama3.1
```

5. Confirm it is available:

```bash
ollama list
```

---

## Step 3: Clone and Setup ClipAI

```bash
git clone https://github.com/<your-username>/ClipAI.git
cd ClipAI
```

Create a Python virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment.

Windows:

```powershell
.\.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Step 4: Configure Environment

Copy the example file:

```bash
cp .env.example .env
```

Adjust local settings as needed:

```bash
USE_GPU=true
OLLAMA_MODEL=llama3.1
WHISPER_MODEL=base
```

If you want credential rotation for multiple Google OAuth apps, set:

```bash
GOOGLE_CREDENTIALS_FILES=credentials/app1.json;credentials/app2.json
```

On macOS/Linux, separate multiple paths with `:` instead of `;`.

---

## Step 5: Verify GPU Support (Optional)

GPU is optional. The pipeline works on CPU too, only slower.

Quick check:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

If you have NVIDIA drivers installed, you can also run:

```bash
nvidia-smi
```

---

## Step 6: Run ClipAI

Ensure Ollama is running in another terminal:

```bash
ollama serve
```

Run the web application:

```powershell
$env:PYTHONIOENCODING = "utf-8"; .\.venv\Scripts\python.exe app.py
```

Or run the direct pipeline:

```bash
python main.py
```

---

## Project Structure

```text
ClipAI/
|-- README.md
|-- SETUP.md
|-- requirements.txt
|-- .env.example
|-- .env                  # local only, do not commit
|-- app.py
|-- worker.py
|-- database.py
|-- modulo1_download.py
|-- modulo2_analise.py
|-- modulo3_edicao.py
|-- downloads/            # generated media
`-- data/                 # local app state
```

---

## Common Issues

### Issue: `ffmpeg not found`

- Confirm FFmpeg is installed with `ffmpeg -version`
- Make sure FFmpeg is in your system PATH
- On Windows, restart the terminal after editing PATH

### Issue: `ollama pull` fails

- Confirm Ollama is installed with `ollama --version`
- Check your internet connection
- Try another model such as `mistral`

### Issue: GPU not detected

- CPU fallback is supported automatically
- If you want GPU acceleration, confirm `nvidia-smi` works
- If needed, set `USE_GPU=false` in `.env`

### Issue: Python module not found

- Make sure the virtual environment is active
- Reinstall dependencies with `pip install -r requirements.txt`
- Confirm Python 3.9+ with `python --version`

---

## Next Steps

1. Start the web app.
2. Add a source video to the queue.
3. Review the generated clips in `downloads/`.
4. Configure a YouTube channel only on your local machine when you need publishing.
