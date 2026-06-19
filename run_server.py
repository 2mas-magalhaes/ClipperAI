"""
run_server.py — Watchdog que mantém o servidor ClipAI SEMPRE a correr.
Se o servidor crashar, reinicia automaticamente com delay exponencial.
Uso:  python run_server.py
"""

import os
import sys
import time
import signal
import subprocess
import logging
from datetime import datetime

# ── Config ──
MAX_RESTART_DELAY = 120          # máximo 2 minutos entre restarts
INITIAL_RESTART_DELAY = 3        # 3 segundos no primeiro restart
HEALTHY_UPTIME = 60              # se correr >60s, reset do delay
LOG_FILE = "data/server_watchdog.log"
VERSION = "1.0"

# ── Garantir que estamos no diretório certo ──
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── Logging ──
os.makedirs("data", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | WATCHDOG | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
    ]
)

# ── Python do venv ──
VENV_PYTHON = os.path.join("venv", "Scripts", "python.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable


def run_server():
    """Lança o app.py como subprocesso e espera que termine."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["WATCHDOG_MANAGED"] = "1"  # flag para o app.py saber que tem watchdog

    cmd = [VENV_PYTHON, "app.py"]

    logging.info(f"▶️  A iniciar servidor: {' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=sys.stdout,      # partilha stdout do watchdog
        stderr=sys.stderr,      # partilha stderr
        creationflags=0,
    )
    return proc


def main():
    restart_delay = INITIAL_RESTART_DELAY
    restart_count = 0

    logging.info("=" * 60)
    logging.info(f"🐕 WATCHDOG ClipAI v{VERSION} iniciado")
    logging.info(f"   Python  : {VENV_PYTHON}")
    logging.info(f"   Dir     : {os.getcwd()}")
    logging.info(f"   Log     : {os.path.abspath(LOG_FILE)}")
    logging.info(f"   URL     : http://localhost:5000")
    logging.info(f"   Restart : delay inicial {INITIAL_RESTART_DELAY}s, máx {MAX_RESTART_DELAY}s")
    logging.info("=" * 60)

    while True:
        start_time = time.time()
        proc = None

        try:
            proc = run_server()
            exit_code = proc.wait()     # bloqueia até o processo terminar
            uptime = time.time() - start_time
            uptime_str = f"{int(uptime // 60)}m{int(uptime % 60)}s"

            if exit_code == 0:
                logging.info("✅ Servidor terminou normalmente (exit 0)")
                break  # Saída limpa = não reiniciar

            # ── Crash / Erro ──
            restart_count += 1
            logging.warning(f"💥 Servidor crashou! (exit {exit_code}) — uptime {uptime_str} — restart #{restart_count}")
            logging.warning(f"   Logs completos em: {os.path.abspath(LOG_FILE)}")

            # Se correu >60s, resetar delay (não é loop infinito de crash)
            if uptime > HEALTHY_UPTIME:
                restart_delay = INITIAL_RESTART_DELAY
                logging.info("   ℹ️ Uptime saudável, reset do delay")
            else:
                # Delay exponencial: 3s, 6s, 12s, 24s... até máx 120s
                restart_delay = min(restart_delay * 2, MAX_RESTART_DELAY)
                logging.warning(f"   ⚡ Uptime baixo ({uptime_str}) — possível crash em loop")

            logging.info(f"🔄 A reiniciar em {restart_delay}s...")
            time.sleep(restart_delay)

        except KeyboardInterrupt:
            logging.info("🛑 Ctrl+C — A parar servidor...")
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logging.warning("   ⚠️ Processo não terminou, a forçar kill...")
                    proc.kill()
            logging.info("👋 Watchdog terminado.")
            break

        except Exception as e:
            import traceback as _tb
            logging.error(f"❌ Erro no watchdog: {e}")
            logging.error(_tb.format_exc())
            restart_count += 1
            time.sleep(restart_delay)
            restart_delay = min(restart_delay * 2, MAX_RESTART_DELAY)


if __name__ == "__main__":
    main()
