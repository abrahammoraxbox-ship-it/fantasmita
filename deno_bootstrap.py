import os
import platform
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
DENO_HOME = os.path.join(BASE, ".deno")
DENO_BIN_DIR = os.path.join(DENO_HOME, "bin")
DENO_BIN = os.path.join(DENO_BIN_DIR, "deno")


def _version(path):
    try:
        p = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=8)
        if p.returncode == 0:
            return (p.stdout or p.stderr or "").strip().splitlines()[0]
    except Exception:
        pass
    return None


def ensure_deno():
    """Asegura Deno local para yt-dlp sin requerir root ni cambiar Wispbyte."""
    # Si Wispbyte ya trae un Deno válido, úsalo.
    existing = shutil.which("deno")
    if existing and _version(existing):
        print(f"🎵 DENO BOOTSTRAP: OK sistema ({_version(existing)})")
        return existing

    os.makedirs(DENO_BIN_DIR, exist_ok=True)

    # Reutiliza la copia persistente del proyecto en reinicios posteriores.
    if os.path.isfile(DENO_BIN):
        try:
            os.chmod(DENO_BIN, os.stat(DENO_BIN).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass
        if _version(DENO_BIN):
            os.environ["PATH"] = DENO_BIN_DIR + os.pathsep + os.environ.get("PATH", "")
            print(f"🎵 DENO BOOTSTRAP: OK local ({_version(DENO_BIN)})")
            return DENO_BIN

    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        asset = "deno-x86_64-unknown-linux-gnu.zip"
    elif machine in {"aarch64", "arm64"}:
        asset = "deno-aarch64-unknown-linux-gnu.zip"
    else:
        print(f"⚠️ DENO BOOTSTRAP: arquitectura no soportada automáticamente: {machine}")
        return None

    url = f"https://github.com/denoland/deno/releases/latest/download/{asset}"
    print(f"🎵 DENO BOOTSTRAP: instalando Deno local para {machine}...")

    try:
        with tempfile.TemporaryDirectory(prefix="fantasmita_deno_") as td:
            archive = os.path.join(td, "deno.zip")
            req = urllib.request.Request(url, headers={"User-Agent": "Fantasmita/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(archive, "wb") as f:
                shutil.copyfileobj(r, f)
            with zipfile.ZipFile(archive) as z:
                if "deno" not in z.namelist():
                    raise RuntimeError("El paquete oficial no contiene el ejecutable deno")
                extracted = z.extract("deno", td)
                shutil.copy2(extracted, DENO_BIN)
        os.chmod(DENO_BIN, 0o755)
        ver = _version(DENO_BIN)
        if not ver:
            raise RuntimeError("Deno se descargó pero no pudo ejecutarse")
        os.environ["PATH"] = DENO_BIN_DIR + os.pathsep + os.environ.get("PATH", "")
        print(f"✅ DENO BOOTSTRAP: {ver} | {DENO_BIN}")
        return DENO_BIN
    except Exception as e:
        print(f"⚠️ DENO BOOTSTRAP ERROR: {e!r}")
        print("⚠️ Fantasmita seguirá iniciando; solo YouTube puede quedar limitado.")
        return None
