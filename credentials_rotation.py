"""
Sistema de rotacao automatica de credenciais Google OAuth quando quota e excedida.
Permite multiplas contas YouTube com ciclo automatico sem hardcodes locais.
"""

import glob
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

ROTATION_STATE_FILE = os.path.join("data", "credentials_rotation.json")
GOOGLE_CREDENTIALS_ENV = "GOOGLE_CREDENTIALS_FILES"
DEFAULT_CREDENTIAL_PATTERNS = (
    "client_secret_*.json",
    "credentials/*.json",
    "secrets/*.json",
)


def _discover_credentials():
    """Descobre ficheiros de credenciais a partir de env var ou patterns locais."""
    configured = os.getenv(GOOGLE_CREDENTIALS_ENV, "").strip()
    items = []

    if configured:
        normalized = configured.replace("\n", os.pathsep).replace(",", os.pathsep).replace(";", os.pathsep)
        items.extend(part.strip() for part in normalized.split(os.pathsep) if part.strip())
    else:
        for pattern in DEFAULT_CREDENTIAL_PATTERNS:
            items.extend(glob.glob(pattern))

    resolved = []
    seen = set()
    for item in items:
        candidate = os.path.normpath(item)
        if not os.path.isfile(candidate):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        resolved.append(candidate)

    return resolved


CREDENTIALS_LIST = _discover_credentials()


def _credential_label(cred_filename):
    base = os.path.basename(cred_filename)
    if base.startswith("client_secret_"):
        rest = base[len("client_secret_"):]
        return rest.split(".")[0]
    return base.replace(".json", "")


def _load_rotation_state():
    """Carrega qual credential está actualmente em uso."""
    try:
        if os.path.exists(ROTATION_STATE_FILE):
            with open(ROTATION_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"current_index": 0, "last_rotated": None}


def _save_rotation_state(state):
    """Guarda estado de rotação."""
    try:
        os.makedirs(os.path.dirname(ROTATION_STATE_FILE), exist_ok=True)
        with open(ROTATION_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        logging.warning(f"⚠️ Erro ao guardar estado de rotação: {e}")


def get_current_credentials():
    """Retorna o caminho do ficheiro de credentials actualmente em uso."""
    if not CREDENTIALS_LIST:
        return None
    state = _load_rotation_state()
    idx = state.get("current_index", 0) % len(CREDENTIALS_LIST)
    return CREDENTIALS_LIST[idx]


def rotate_credentials():
    """
    Rota para o próximo credentials (quando quota é excedida).
    Retorna o novo caminho ou None se falharem todos.
    """
    if len(CREDENTIALS_LIST) < 2:
        logging.warning("Rotacao de credenciais indisponivel: menos de 2 credenciais configuradas.")
        return get_current_credentials()

    state = _load_rotation_state()
    current_idx = state.get("current_index", 0)
    old_cred = CREDENTIALS_LIST[current_idx % len(CREDENTIALS_LIST)]
    
    # Ir para o próximo
    next_idx = (current_idx + 1) % len(CREDENTIALS_LIST)
    new_cred = CREDENTIALS_LIST[next_idx % len(CREDENTIALS_LIST)]
    
    state["current_index"] = next_idx
    
    from datetime import datetime
    state["last_rotated"] = datetime.now().isoformat()
    
    _save_rotation_state(state)
    
    # Remover token antigo (força re-autenticação)
    _remove_token_for_credential(old_cred)
    
    logging.warning(f"🔄 Quota excedida! Rotacionando credenciais:")
    logging.warning(f"   ❌ De: {_credential_label(old_cred)}")
    logging.warning(f"   ✅ Para: {_credential_label(new_cred)}")
    logging.warning(f"   ⏰ Próxima rotação possível em 24h")
    
    return new_cred


def _remove_token_for_credential(cred_filename):
    """Remove o token armazenado para forçar re-autenticação."""
    token_file = cred_filename.replace(".json", "_token.json")
    if os.path.exists(token_file):
        try:
            os.remove(token_file)
            logging.debug(f"🗂️  Token removido: {token_file}")
        except Exception as e:
            logging.warning(f"⚠️ Erro ao remover token: {e}")


def get_rotation_status():
    """Retorna status atual da rotação."""
    if not CREDENTIALS_LIST:
        return {
            "current_credentials": None,
            "current_index": 0,
            "total_credentials": 0,
            "last_rotated": None,
            "credentials_list": [],
            "configured_via_env": bool(os.getenv(GOOGLE_CREDENTIALS_ENV, "").strip()),
            "env_var": GOOGLE_CREDENTIALS_ENV,
        }

    state = _load_rotation_state()
    current_idx = state.get("current_index", 0) % len(CREDENTIALS_LIST)
    current_cred = CREDENTIALS_LIST[current_idx]
    
    return {
        "current_credentials": current_cred,
        "current_index": current_idx,
        "total_credentials": len(CREDENTIALS_LIST),
        "last_rotated": state.get("last_rotated"),
        "configured_via_env": bool(os.getenv(GOOGLE_CREDENTIALS_ENV, "").strip()),
        "env_var": GOOGLE_CREDENTIALS_ENV,
        "credentials_list": [
            {
                "index": i,
                "name": _credential_label(cred),
                "file": cred,
                "active": (i == current_idx)
            }
            for i, cred in enumerate(CREDENTIALS_LIST)
        ]
    }
