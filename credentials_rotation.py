"""
Sistema de rotação automática de credenciais Google OAuth quando quota é excedida.
Permite múltiplas contas YouTube com ciclo automático.
"""

import os
import json
import logging
from pathlib import Path

ROTATION_STATE_FILE = os.path.join("data", "credentials_rotation.json")

# Lista de credentials (em ordem de rotação)
CREDENTIALS_LIST = [
    "client_secret_323729487453-eubmo81fr4ac8sedtf3fan61ibqb1i49.apps.googleusercontent.com.json",  # Novo
    "client_secret_856036187225-80u8fna6cdjm2oqbr2q4rtcopdjjeet1.apps.googleusercontent.com.json",  # Antigo
]


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
    state = _load_rotation_state()
    idx = state.get("current_index", 0) % len(CREDENTIALS_LIST)
    return CREDENTIALS_LIST[idx]


def rotate_credentials():
    """
    Rota para o próximo credentials (quando quota é excedida).
    Retorna o novo caminho ou None se falharem todos.
    """
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
    state = _load_rotation_state()
    current_idx = state.get("current_index", 0) % len(CREDENTIALS_LIST)
    current_cred = CREDENTIALS_LIST[current_idx]
    
    return {
        "current_credentials": current_cred,
        "current_index": current_idx,
        "total_credentials": len(CREDENTIALS_LIST),
        "last_rotated": state.get("last_rotated"),
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
