# ClipAI CV Cleanup And Satisfying Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preparar o ClipAI para portfolio/CV, remover a experiencia Clippy incompleta, adicionar controlo para usar ou nao videos satisfying, e finalizar com um historico Git limpo.

**Architecture:** A decisao "usar satisfying video" fica guardada como setting global e tambem como opcao por item da queue. O worker le a opcao do item no momento de edicao e passa-a para `modulo3_edicao.py`; quando estiver desligada, o pipeline usa sempre o layout full-screen existente.

**Tech Stack:** Python 3.9+, Flask, JSON local DB, vanilla JS/CSS, FFmpeg/OpenCV, unittest/compileall para validacao local.

---

## File Structure

- Modify `database.py`: adicionar default `usar_video_satisfatorio`, guardar a flag em novos itens da queue, migrar settings e itens antigos.
- Modify `app.py`: aceitar `usar_video_satisfatorio` em `/api/queue`, `/api/queue/upload`, e em bulk/patch se necessario.
- Modify `worker.py`: resolver a opcao final por item, com fallback para settings, e passa-la a `editar_clipes()`.
- Modify `modulo3_edicao.py`: remover imports e passos Clippy, adicionar parametros `usar_video_satisfatorio` em `editar_clipes()`, `aplicar_edicao_profissional()`, `_aplicar_edicao_standard()`, e saltar `_encontrar_video_satisfatorio()` quando a opcao estiver desligada.
- Modify `templates/index.html`: adicionar checkbox global em Definicoes e checkbox por video no modal "Adicionar Video".
- Modify `static/app.js`: preencher, guardar e enviar a nova opcao no fluxo YouTube e upload local.
- Modify `README.md`, `SETUP.md`, `.env.example` if needed: remover referencias Clippy, atualizar comandos de validacao e destacar o produto para CV.
- Modify `requirements.txt`: remover dependencias so usadas por Clippy, depois de confirmar `rg -n "PIL|Pillow|edge_tts|edge-tts"`.
- Delete `personagem_clippy.py`, `test_clippy_v3.py`, `exemplos_clippy.py`, `CLIPPY_README.md`, `CLIPPY_RESUMO.md`, `CLIPPY_2.0_FEATURES.md`, `INSTALL_CLIPPY.md`.
- Create `test_layout_options.py`: testes unitarios pequenos para a flag de satisfying e defaults da queue.

---

### Task 1: Create A Safety Branch And Baseline

**Files:**
- No file edits.

- [ ] **Step 1: Confirm clean worktree**

Run:

```powershell
git status --short
```

Expected: no output. If there is output, inspect it and do not overwrite unrelated user work.

- [ ] **Step 2: Create safety refs**

Run:

```powershell
git branch backup/main-before-cv-cleanup
git tag backup-main-before-cv-cleanup-2026-06-05
git switch -c cv-cleanup
```

Expected: new branch `cv-cleanup` checked out.

- [ ] **Step 3: Run baseline validation**

Run:

```powershell
python -m compileall app.py worker.py database.py modulo1_download.py modulo2_analise.py modulo3_edicao.py personagem_clippy.py
```

Expected: all files compile. If this fails before edits, save the failure text in the final notes and continue with focused changes.

---

### Task 2: Remove The Clippy Experiment

**Files:**
- Modify: `modulo3_edicao.py`
- Modify: `README.md`
- Modify: `requirements.txt`
- Delete: `personagem_clippy.py`
- Delete: `test_clippy_v3.py`
- Delete: `exemplos_clippy.py`
- Delete: `CLIPPY_README.md`
- Delete: `CLIPPY_RESUMO.md`
- Delete: `CLIPPY_2.0_FEATURES.md`
- Delete: `INSTALL_CLIPPY.md`

- [ ] **Step 1: Write the failing guard search**

Run:

```powershell
rg -n "clippy|personagem_clippy|adicionar_intro_clippy|adicionar_intervencoes_clippy|edge-tts|Pillow" -S .
```

Expected before implementation: matches in `modulo3_edicao.py`, README/docs, requirements, and Clippy files.

- [ ] **Step 2: Remove Clippy import block in `modulo3_edicao.py`**

Replace the current Clippy import block near the top of `modulo3_edicao.py` with nothing. The removed block starts with:

```python
# Importa modulo da personagem Clippy (AI que da hooks no inicio)
try:
    from personagem_clippy import (
        gerar_hook_com_ai,
        criar_intro_clippy,
        concatenar_intro_com_video,
        gerar_intervencoes_satiricas,
        inserir_intervencoes_clippy,
        criar_personagem_clippy
    )
    CLIPPY_DISPONIVEL = True
except ImportError:
    CLIPPY_DISPONIVEL = False
    print("Modulo personagem_clippy nao disponivel. Intros do Clippy desativadas.")
```

- [ ] **Step 3: Simplify `editar_clipes()` signature**

In `modulo3_edicao.py`, change:

```python
def editar_clipes(caminho_video, clipes, segmentos_whisper, pasta_saida="downloads/clips_editados",
                  progress_callback=None, unique_id=None, adicionar_intro_clippy=True,
                  adicionar_intervencoes_clippy=True):
```

to:

```python
def editar_clipes(caminho_video, clipes, segmentos_whisper, pasta_saida="downloads/clips_editados",
                  progress_callback=None, unique_id=None, usar_video_satisfatorio=True):
```

Update the docstring by replacing the Clippy steps with:

```python
      4. Aplica loop infinito seamless

    Args:
        progress_callback (callable): Funcao callback(clip_idx, total_clips, pct, detail)
        unique_id (str): Identificador unico para prefixar os nomes dos ficheiros (ex: queue_id)
        usar_video_satisfatorio (bool): Se True, tenta layout split com video satisfying. Se False, usa full-screen.
```

- [ ] **Step 4: Delete Clippy processing block**

In `modulo3_edicao.py`, remove the whole section from:

```python
# PASSO 3.5: INTRO CLIPPY
```

through the end of:

```python
# PASSO 3.8: INTERVENCOES SATIRICAS DA CLIPPY
```

Then replace the loop input setup with:

```python
caminho_base_loop = caminho_preloop
```

And update the loop call:

```python
duracao_real = obter_duracao_video(caminho_base_loop) or duracao_clip
sucesso_loop = aplicar_loop_infinito(caminho_base_loop, caminho_final, duracao_real)
if not sucesso_loop:
    print("  Loop infinito falhou, usando versao sem loop")
    shutil.copy2(caminho_base_loop, caminho_final)
```

Remove cleanup blocks for `caminho_com_clippy` and `caminho_com_intervencoes`.

- [ ] **Step 5: Delete Clippy files**

Run:

```powershell
Remove-Item -LiteralPath personagem_clippy.py
Remove-Item -LiteralPath test_clippy_v3.py
Remove-Item -LiteralPath exemplos_clippy.py
Remove-Item -LiteralPath CLIPPY_README.md
Remove-Item -LiteralPath CLIPPY_RESUMO.md
Remove-Item -LiteralPath CLIPPY_2.0_FEATURES.md
Remove-Item -LiteralPath INSTALL_CLIPPY.md
```

Expected: files removed from worktree.

- [ ] **Step 6: Remove Clippy dependencies**

In `requirements.txt`, remove:

```text
# Image processing and Clippy character rendering
Pillow>=10.0.0

# Text-to-speech
edge-tts>=6.1.9
```

Only keep `Pillow` if `rg -n "from PIL|import PIL|Pillow" -S .` shows a non-Clippy use.

- [ ] **Step 7: Update README**

In `README.md`, remove:

```text
- "Clippy" character utilities for animated hooks, voice, and interventions.
|-- personagem_clippy.py      # Clippy character rendering, TTS, hooks
python -m compileall app.py worker.py database.py modulo1_download.py modulo2_analise.py modulo3_edicao.py personagem_clippy.py
| `test_clippy_v3.py` | Exercises Clippy rendering, animation, TTS, and AI hooks. | Requires FFmpeg and may require network/Ollama. |
```

Replace compile commands with:

```powershell
python -m compileall app.py worker.py database.py modulo1_download.py modulo2_analise.py modulo3_edicao.py
```

- [ ] **Step 8: Verify no Clippy references remain**

Run:

```powershell
rg -n "clippy|personagem_clippy|adicionar_intro_clippy|adicionar_intervencoes_clippy|edge-tts" -S .
```

Expected: no matches, except possibly old Git plan text if this plan remains in the repo. If the plan is committed, ignore matches under `docs/superpowers/plans/`.

- [ ] **Step 9: Commit**

Run:

```powershell
git add modulo3_edicao.py README.md requirements.txt
git add -u
git commit -m "chore: remove unfinished Clippy experiment"
```

---

### Task 3: Add Satisfying Video Toggle Through The Backend

**Files:**
- Modify: `database.py`
- Modify: `app.py`
- Modify: `worker.py`
- Modify: `modulo3_edicao.py`
- Test: `test_layout_options.py`

- [ ] **Step 1: Write failing tests**

Create `test_layout_options.py`:

```python
import os
import tempfile
import unittest

import database as db
import modulo3_edicao as ed


class LayoutOptionTests(unittest.TestCase):
    def test_queue_item_stores_satisfying_flag(self):
        original_path = db.DB_PATH
        with tempfile.TemporaryDirectory() as tmp:
            db.DB_PATH = os.path.join(tmp, "clipai_db.json")
            item = db.add_to_queue(
                "https://example.com/video",
                title="Demo",
                usar_video_satisfatorio=False,
            )
            try:
                self.assertFalse(item["usar_video_satisfatorio"])
                self.assertFalse(db.get_queue()[0]["usar_video_satisfatorio"])
                self.assertTrue(db.get_settings()["usar_video_satisfatorio"])
            finally:
                db.DB_PATH = original_path

    def test_fullscreen_layout_does_not_lookup_satisfying_video_when_disabled(self):
        calls = {}
        original_find = ed._encontrar_video_satisfatorio
        original_fps = ed.obter_fps_video
        original_encode = ed._encode_com_filtros

        def fail_find():
            raise AssertionError("_encontrar_video_satisfatorio should not be called")

        def fake_encode(caminho_video, caminho_saida, vf=None, filter_complex=None, duracao_clip=None):
            calls["filter_complex"] = filter_complex
            return True

        ed._encontrar_video_satisfatorio = fail_find
        ed.obter_fps_video = lambda _: 30
        ed._encode_com_filtros = fake_encode
        try:
            ok = ed._aplicar_edicao_standard(
                "input.mp4",
                None,
                "output.mp4",
                12,
                1920,
                1080,
                usar_video_satisfatorio=False,
            )
            self.assertTrue(ok)
            self.assertIn("scale=1080:1920", calls["filter_complex"])
        finally:
            ed._encontrar_video_satisfatorio = original_find
            ed.obter_fps_video = original_fps
            ed._encode_com_filtros = original_encode

    def test_split_layout_uses_satisfying_video_when_enabled(self):
        calls = {}
        original_find = ed._encontrar_video_satisfatorio
        original_fps = ed.obter_fps_video
        original_duration = ed._obter_duracao_video
        original_encode_2in = ed._encode_com_filtros_2in

        def fake_encode_2in(caminho_video, caminho_video2, caminho_saida, filter_complex, duracao):
            calls["video2"] = caminho_video2
            calls["filter_complex"] = filter_complex
            return True

        ed._encontrar_video_satisfatorio = lambda: "sat.mp4"
        ed.obter_fps_video = lambda _: 30
        ed._obter_duracao_video = lambda _: 120
        ed._encode_com_filtros_2in = fake_encode_2in
        try:
            ok = ed._aplicar_edicao_standard(
                "input.mp4",
                None,
                "output.mp4",
                12,
                1920,
                1080,
                usar_video_satisfatorio=True,
            )
            self.assertTrue(ok)
            self.assertEqual("sat.mp4", calls["video2"])
            self.assertIn("vstack=inputs=2", calls["filter_complex"])
        finally:
            ed._encontrar_video_satisfatorio = original_find
            ed.obter_fps_video = original_fps
            ed._obter_duracao_video = original_duration
            ed._encode_com_filtros_2in = original_encode_2in


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m unittest test_layout_options.py -v
```

Expected: fail because `usar_video_satisfatorio` is not yet supported.

- [ ] **Step 3: Add defaults and queue storage in `database.py`**

In `_default_db()["settings"]`, add:

```python
"usar_video_satisfatorio": True,
```

Update both queue creation functions:

```python
def add_to_queue(url, title="", channel_id=None, priority=0, auto_publish=None, usar_video_satisfatorio=None):
```

and:

```python
def add_to_queue_with_meta(url, title="", channel_id=None, priority=0, source_video_id=None, source_channel_name="", auto_publish=None, usar_video_satisfatorio=None):
```

Before `item = { ... }`, add:

```python
if usar_video_satisfatorio is None:
    usar_video_satisfatorio = bool(db.get("settings", {}).get("usar_video_satisfatorio", True))
```

Inside each `item` dict, add:

```python
"usar_video_satisfatorio": bool(usar_video_satisfatorio),
```

In `_load()`, after settings migration, add:

```python
for item in db.get("queue", []):
    if "usar_video_satisfatorio" not in item:
        item["usar_video_satisfatorio"] = bool(db.get("settings", {}).get("usar_video_satisfatorio", True))
```

- [ ] **Step 4: Accept the flag in `app.py`**

In `/api/queue`, pass:

```python
usar_video_satisfatorio=data.get("usar_video_satisfatorio"),
```

In `/api/queue/upload`, read:

```python
usar_video_satisfatorio = request.form.get("usar_video_satisfatorio", "1") == "1"
```

and pass it to `db.add_to_queue(...)`:

```python
usar_video_satisfatorio=usar_video_satisfatorio,
```

Optional bulk action in `api_bulk_queue()`:

```python
elif action == "set_satisfying_video":
    value = bool(data.get("usar_video_satisfatorio", data.get("value", True)))
    for item_id in ids:
        r = db.update_queue_item(item_id, usar_video_satisfatorio=value)
        if r:
            results["updated"] += 1
```

- [ ] **Step 5: Pass the flag from `worker.py`**

Before calling `editar_clipes(...)`, add:

```python
settings = db.get_settings()
usar_video_satisfatorio = item.get(
    "usar_video_satisfatorio",
    settings.get("usar_video_satisfatorio", True),
)
```

Update the call:

```python
clipes_editados = editar_clipes(
    caminho_video,
    clipes,
    segmentos_whisper,
    progress_callback=edit_progress_callback,
    unique_id=item_id,
    usar_video_satisfatorio=bool(usar_video_satisfatorio),
)
```

- [ ] **Step 6: Thread the flag through `modulo3_edicao.py`**

Change:

```python
def aplicar_edicao_profissional(caminho_video, caminho_ass, caminho_saida, duracao_clip,
                                intervalos_fala=None, face_info=None):
```

to:

```python
def aplicar_edicao_profissional(caminho_video, caminho_ass, caminho_saida, duracao_clip,
                                intervalos_fala=None, face_info=None,
                                usar_video_satisfatorio=True):
```

Pass it to `_aplicar_edicao_standard(...)`:

```python
return _aplicar_edicao_standard(
    caminho_video,
    caminho_ass,
    caminho_saida,
    duracao_clip,
    w,
    h,
    intervalos_fala=intervalos_fala,
    face_info=face_info,
    usar_video_satisfatorio=usar_video_satisfatorio,
)
```

Change `_aplicar_edicao_standard(...)` signature:

```python
def _aplicar_edicao_standard(caminho_video, caminho_ass, caminho_saida,
                             duracao_clip, w, h,
                             intervalos_fala=None, face_info=None,
                             usar_video_satisfatorio=True):
```

Replace:

```python
video_sat = _encontrar_video_satisfatorio()
```

with:

```python
video_sat = _encontrar_video_satisfatorio() if usar_video_satisfatorio else None
if not usar_video_satisfatorio:
    print("  Layout satisfying desativado - usando full-screen")
```

Update the call to `aplicar_edicao_profissional(...)` inside `editar_clipes()`:

```python
sucesso = aplicar_edicao_profissional(
    caminho_cortado,
    caminho_ass,
    caminho_preloop,
    duracao_clip,
    intervalos_fala=intervalos_fala,
    face_info=face_info,
    usar_video_satisfatorio=usar_video_satisfatorio,
)
```

- [ ] **Step 7: Run backend tests**

Run:

```powershell
python -m unittest test_layout_options.py -v
python -m compileall app.py worker.py database.py modulo1_download.py modulo2_analise.py modulo3_edicao.py
```

Expected: tests pass and compileall succeeds.

- [ ] **Step 8: Commit**

Run:

```powershell
git add database.py app.py worker.py modulo3_edicao.py test_layout_options.py
git commit -m "feat: add satisfying video layout toggle"
```

---

### Task 4: Add Dashboard Controls

**Files:**
- Modify: `templates/index.html`
- Modify: `static/app.js`

- [ ] **Step 1: Add global setting UI**

In `templates/index.html`, near the existing `setting-auto-publish` checkbox, add:

```html
<div class="form-group">
    <label class="checkbox-label">
        <input type="checkbox" id="setting-usar-video-satisfatorio">
        <span>Usar video satisfying no layout final</span>
    </label>
    <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">Se desativado, os clips usam o video principal em tela inteira.</div>
</div>
```

- [ ] **Step 2: Add per-video checkbox UI**

In the "Comum" area of `templates/index.html`, near `video-auto-publish`, add:

```html
<div class="form-group">
    <label class="checkbox-label">
        <input type="checkbox" id="video-usar-video-satisfatorio">
        <span>Usar video satisfying neste video</span>
    </label>
    <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">Desativa para gerar o clip em tela inteira.</div>
</div>
```

- [ ] **Step 3: Render and save global setting in `static/app.js`**

In `renderSettings()`, add:

```javascript
document.getElementById('setting-usar-video-satisfatorio').checked = settingsData.usar_video_satisfatorio !== false;
```

In `saveSettings()`, add:

```javascript
usar_video_satisfatorio: document.getElementById('setting-usar-video-satisfatorio').checked,
```

- [ ] **Step 4: Default modal checkbox from settings**

In `openAddVideoModal()`, add:

```javascript
document.getElementById('video-usar-video-satisfatorio').checked = settingsData.usar_video_satisfatorio !== false;
```

- [ ] **Step 5: Send flag for YouTube queue items**

In `addVideoYoutube()`, add:

```javascript
const usarVideoSatisfatorio = document.getElementById('video-usar-video-satisfatorio').checked;
```

Update the API payload:

```javascript
await api('/api/queue', 'POST', {
    url,
    title,
    channel_id: channelId || null,
    auto_publish: autoPublish,
    usar_video_satisfatorio: usarVideoSatisfatorio,
});
```

- [ ] **Step 6: Send flag for local uploads**

In `addVideoFromFile()`, add:

```javascript
const usarVideoSatisfatorio = document.getElementById('video-usar-video-satisfatorio').checked;
```

Append to `formData`:

```javascript
formData.append('usar_video_satisfatorio', usarVideoSatisfatorio ? '1' : '0');
```

- [ ] **Step 7: Manual UI verification**

Run:

```powershell
python app.py
```

Open `http://localhost:5000` and verify:

- Definicoes shows "Usar video satisfying no layout final".
- Add Video modal shows "Usar video satisfying neste video".
- With checkbox off, `/api/queue` stores `"usar_video_satisfatorio": false`.
- Upload local sends `usar_video_satisfatorio=0` when off.

- [ ] **Step 8: Commit**

Run:

```powershell
git add templates/index.html static/app.js
git commit -m "feat: expose satisfying layout controls"
```

---

### Task 5: Polish The Project For CV

**Files:**
- Modify: `README.md`
- Modify: `SETUP.md`
- Modify: `.env.example`
- Optional create: `docs/PORTFOLIO_NOTES.md`

- [ ] **Step 1: Rewrite README feature story**

In `README.md`, make the feature list focus on:

```text
- Queue-based web dashboard for long-form video ingestion, processing, review, and publishing.
- Local AI transcription and clip selection with Faster-Whisper and Ollama.
- FFmpeg/OpenCV vertical editing with subtitles, face-aware framing, optional satisfying split layout, and full-screen fallback.
- Review-first publishing workflow with optional auto-publish and YouTube OAuth rotation.
- Local JSON persistence for a self-contained automation demo.
```

- [ ] **Step 2: Update architecture block**

Ensure the project structure omits Clippy and includes:

```text
|-- modulo3_edicao.py         # FFmpeg/OpenCV editing pipeline and layout selection
|-- test_layout_options.py    # Unit tests for layout option behavior
```

- [ ] **Step 3: Add portfolio-ready validation section**

Add:

```markdown
## Validation

```powershell
python -m unittest test_layout_options.py -v
python -m compileall app.py worker.py database.py modulo1_download.py modulo2_analise.py modulo3_edicao.py
```

The repository also contains script-style smoke checks for publishing and editing flows. Full end-to-end media generation requires FFmpeg, FFprobe, Ollama, and sample video input.
```

- [ ] **Step 4: Add honest limitations**

Add a short section:

```markdown
## Current Limitations

- The application is designed for local automation rather than hosted multi-user deployment.
- End-to-end video processing depends on local FFmpeg, FFprobe, Whisper model downloads, and an Ollama model.
- YouTube publishing requires user-provided OAuth credentials that must remain outside Git.
```

- [ ] **Step 5: Clean runtime artifacts**

Run:

```powershell
git status --short
rg -n "client_secret|refresh_token|access_token|AIza|ya29\\.|password|secret" -S . --glob "!venv/**" --glob "!data/**" --glob "!downloads/**"
```

Expected: no committed secrets. Do not delete local `.env`, `data/`, or `downloads/` unless explicitly requested.

- [ ] **Step 6: Commit**

Run:

```powershell
git add README.md SETUP.md .env.example docs/PORTFOLIO_NOTES.md
git commit -m "docs: polish project for portfolio review"
```

If `docs/PORTFOLIO_NOTES.md` is not created, omit it from `git add`.

---

### Task 6: Final Verification

**Files:**
- No expected edits unless verification reveals issues.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m unittest test_layout_options.py -v
```

Expected: all tests pass.

- [ ] **Step 2: Run compile validation**

Run:

```powershell
python -m compileall app.py worker.py database.py modulo1_download.py modulo2_analise.py modulo3_edicao.py
```

Expected: all files compile.

- [ ] **Step 3: Confirm Clippy removal**

Run:

```powershell
rg -n "clippy|personagem_clippy|adicionar_intro_clippy|adicionar_intervencoes_clippy|edge-tts" -S . --glob "!docs/superpowers/plans/**"
```

Expected: no matches.

- [ ] **Step 4: Confirm satisfying flag path**

Run:

```powershell
rg -n "usar_video_satisfatorio|video-usar-video-satisfatorio|setting-usar-video-satisfatorio" database.py app.py worker.py modulo3_edicao.py templates\\index.html static\\app.js test_layout_options.py
```

Expected: matches in all listed files.

- [ ] **Step 5: Commit fixes if verification required changes**

Run:

```powershell
git add .
git commit -m "test: verify layout option behavior"
```

Only run this commit if Task 6 produced code/doc changes not already committed.

---

### Task 7: Rewrite Commit History For A Clean CV Branch

**Files:**
- Git metadata only.

- [ ] **Step 1: Review current history**

Run:

```powershell
git log --oneline --decorate --graph --all -n 40
```

Current known issues:

- Several commits are named `"."`.
- There are merge commits from `main`.
- Clippy branches exist and should not be the story shown to recruiters.

- [ ] **Step 2: Choose history strategy**

Recommended for a CV repo:

```text
Strategy A: Curated linear history on main
- Rebase/squash/rename existing commits.
- Force push with --force-with-lease.
- Best when nobody else depends on the remote branch.

Strategy B: New portfolio branch
- Keep main as-is.
- Publish `portfolio/main` or `cv-cleanup`.
- Best when avoiding force-push risk.
```

Use Strategy A only if the remote is yours alone.

- [ ] **Step 3: Interactive rebase with backup**

Run:

```powershell
git branch backup/pre-history-rewrite
git tag backup-pre-history-rewrite-2026-06-05
git rebase -i --rebase-merges --root
```

In the editor:

- Rename `"."` commits to meaningful conventional messages.
- Squash tiny README-only updates into one docs commit.
- Keep security cleanup as its own commit.
- Keep the new cleanup/toggle commits separate.

Suggested final story:

```text
feat: scaffold local video automation pipeline
feat: add Flask dashboard and queue worker
feat: add AI transcription and clip analysis flow
feat: add FFmpeg vertical editing pipeline
feat: add review and YouTube publishing workflow
chore: add local config template and security ignores
docs: add professional setup and README
chore: remove unfinished Clippy experiment
feat: add satisfying video layout toggle
feat: expose satisfying layout controls
docs: polish project for portfolio review
```

- [ ] **Step 4: Verify after rewrite**

Run:

```powershell
python -m unittest test_layout_options.py -v
python -m compileall app.py worker.py database.py modulo1_download.py modulo2_analise.py modulo3_edicao.py
git log --oneline --decorate --graph -n 20
```

Expected: tests pass, compileall succeeds, commit messages look intentional.

- [ ] **Step 5: Push safely**

If using Strategy A:

```powershell
git push --force-with-lease origin main
```

If using Strategy B:

```powershell
git push -u origin cv-cleanup
```

---

## Self-Review

- Spec coverage: Clippy removal is covered in Task 2. Satisfying video toggle and full-screen fallback are covered in Tasks 3 and 4. CV cleanup is covered in Task 5. Commit renaming/history cleanup is covered in Task 7.
- Placeholder scan: no placeholder markers remain; each code-changing task includes concrete snippets or exact commands.
- Type consistency: the new flag is consistently named `usar_video_satisfatorio` in Python/JSON and `video-usar-video-satisfatorio` or `setting-usar-video-satisfatorio` for DOM ids.

---

## Execution Options

Plan complete. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session with checkpoints.
