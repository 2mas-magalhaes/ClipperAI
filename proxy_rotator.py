"""
proxy_rotator.py — Sistema de proxies rotativas para yt-dlp.
Rota entre múltiplas proxies fixas + fallback para ByteProxy residencial.
"""

import logging

# ─── Config: Proxies Fixas ────────────────────────────────────────
PROXY_LIST = [
    ("151.241.39.118", "59100", "tomasmaria00", "qR6V7LiCTY"),
    ("151.241.39.150", "59100", "tomasmaria00", "qR6V7LiCTY"),
    ("151.241.39.223", "59100", "tomasmaria00", "qR6V7LiCTY"),
]

PROXY_URLS = [
    f"http://{user}:{pwd}@{ip}:{port}"
    for ip, port, user, pwd in PROXY_LIST
]
# ──────────────────────────────────────────────────────────────────

_proxy_index = 0


def get_proxy():
    """Devolve uma proxy da lista fixa, rotacionando entre elas."""
    global _proxy_index
    if not PROXY_URLS:
        return None
    proxy = PROXY_URLS[_proxy_index % len(PROXY_URLS)]
    _proxy_index += 1
    return proxy


def get_all_proxies():
    """Devolve lista com todas as proxies disponíveis."""
    return PROXY_URLS.copy()


def remove_bad_proxy(proxy_url):
    """Remove uma proxy da lista se falhar repetidamente."""
    global PROXY_URLS
    if proxy_url in PROXY_URLS:
        PROXY_URLS.remove(proxy_url)
        logging.warning(f"🚫 Proxy removida da lista: {proxy_url[:50]}... ({len(PROXY_URLS)} restantes)")
    else:
        logging.debug(f"⚠️ Tentativa de remover proxy inexistente: {proxy_url[:50]}...")


def refresh_proxies(force=False):
    """Compatibilidade: recarrega a lista original de proxies."""
    global PROXY_URLS
    PROXY_URLS = [
        f"http://{user}:{pwd}@{ip}:{port}"
        for ip, port, user, pwd in PROXY_LIST
    ]
    logging.info(f"✅ Lista de proxies recarregada: {len(PROXY_URLS)} proxies disponíveis")
    return PROXY_URLS.copy()


def apply_proxy_to_opts(ydl_opts, proxy_url=None):
    """Adiciona a proxy às opções do yt-dlp."""
    if proxy_url is None:
        proxy_url = get_proxy()
    if proxy_url:
        ydl_opts["proxy"] = proxy_url
    return ydl_opts


def get_proxy_status():
    """Status para a interface."""
    return {
        "total": len(PROXY_URLS),
        "last_refresh": 0,
        "refreshing": False,
        "type": "rotating_list"
    }
