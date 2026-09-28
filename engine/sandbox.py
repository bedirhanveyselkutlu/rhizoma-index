"""Rhizoma Sandbox Katmanı (Docker & İzole Container İzolasyonu).
Yabancı repo'ları ve agent kodlarını host sistemden tamamen izole edilmiş
güvenli Linux container'larında (Docker) çalıştırır.

Kaynak Limitleri:
- Bellek: 2048 MB
- CPU: 2 çekirdek
- PIDs Limit: 1024 (Jest/Node worker'larının EAGAIN çökmesini önler)
- Yetkiler: --cap-drop=ALL, --security-opt no-new-privileges
"""
import os
import shutil
import subprocess
import uuid
from typing import Optional, Dict, Any, List

DOCKER_IMAGES = {
    "python": "python:3.12-slim",
    "javascript": "node:20-slim",
    "php": "php:8.3-cli",
    "default": "python:3.12-slim"
}


def is_docker_available() -> bool:
    """Docker daemon'ın çalışıp çalışmadığını test eder."""
    try:
        docker_bin = shutil.which("docker") or "docker"
        r = subprocess.run([docker_bin, "info"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


class LocalRunner:
    """Yerel makinede subprocess ile çalıştırma (yalnızca yerel güvenilir kodlar için)."""
    name = "Local (Subprocess)"

    def __init__(self, workdir: str):
        self.workdir = workdir

    def run(self, cmd: List[str], timeout: int = 300, network: bool = True) -> dict:
        try:
            r = subprocess.run(
                cmd, cwd=self.workdir, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=timeout, shell=(os.name == "nt")
            )
            return {"ok": r.returncode == 0, "code": r.returncode,
                    "out": r.stdout or "", "err": r.stderr or ""}
        except subprocess.TimeoutExpired:
            return {"ok": False, "code": None, "out": "", "err": f"Zaman aşımı ({timeout}sn)."}
        except Exception as e:
            return {"ok": False, "code": None, "out": "", "err": str(e)[:400]}

    def copy_out(self, container_file_rel: str, host_dst_path: str) -> bool:
        src = os.path.join(self.workdir, container_file_rel)
        if os.path.exists(src) and src != host_dst_path:
            try:
                shutil.copy2(src, host_dst_path)
                return True
            except Exception:
                pass
        return os.path.exists(host_dst_path) or os.path.exists(src)

    def cleanup(self):
        pass


class DockerRunner:
    """İzole Docker container içinde güvenli çalıştırma."""
    name = "Docker Sandbox (İzole)"

    def __init__(self, host_workdir: str, lang: str = "python"):
        self.host_workdir = host_workdir
        self.lang = lang.lower()
        self.image = DOCKER_IMAGES.get(self.lang, DOCKER_IMAGES["default"])
        self.container_name = f"rz_sbx_{uuid.uuid4().hex[:10]}"
        self.docker_bin = shutil.which("docker") or "docker"
        self._created = False
        self._network_disconnected = False

    def _ensure_container(self) -> bool:
        if self._created:
            return True
        
        # 1024 pids-limit + 2GB bellek ile Node.js Jest worker'ları sorunsuz çalışır
        cmd = [
            self.docker_bin, "run", "-d",
            "--name", self.container_name,
            "--memory=2048m",
            "--cpus=2.0",
            "--pids-limit=1024",
            "--security-opt", "no-new-privileges",
            "--cap-drop=ALL",
            "-w", "/work",
            self.image,
            "tail", "-f", "/dev/null"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return False
        
        self._created = True

        # Host dizinini container içine kopyala (cwd ile Windows C: harfi karmaşasını önler)
        try:
            cp_cmd = [self.docker_bin, "cp", ".", f"{self.container_name}:/work/"]
            r_cp = subprocess.run(cp_cmd, cwd=self.host_workdir, capture_output=True, text=True, timeout=60)
            return r_cp.returncode == 0
        except Exception:
            return False

    def disconnect_network(self) -> bool:
        """Container ağını tamamen keser (internetsiz test fazı)."""
        if not self._created or self._network_disconnected:
            return True
        cmd = [self.docker_bin, "network", "disconnect", "bridge", self.container_name]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        self._network_disconnected = True
        return r.returncode == 0

    def run(self, cmd: List[str], timeout: int = 300, network: bool = True) -> dict:
        if not self._ensure_container():
            return {"ok": False, "code": None, "out": "", "err": "Docker container başlatılamadı."}

        if not network and not self._network_disconnected:
            self.disconnect_network()

        exec_cmd = [self.docker_bin, "exec", self.container_name] + cmd
        try:
            r = subprocess.run(
                exec_cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout
            )
            return {"ok": r.returncode == 0, "code": r.returncode,
                    "out": r.stdout or "", "err": r.stderr or ""}
        except subprocess.TimeoutExpired:
            return {"ok": False, "code": None, "out": "", "err": f"Container zaman aşımı ({timeout}sn)."}
        except Exception as e:
            return {"ok": False, "code": None, "out": "", "err": str(e)[:400]}

    def copy_out(self, container_file_rel: str, host_dst_path: str) -> bool:
        """Container içindeki rapor dosyasını host'a çeker."""
        if not self._created:
            return False
        src = f"{self.container_name}:/work/{container_file_rel.lstrip('/')}"
        try:
            dst_dir = os.path.dirname(os.path.abspath(host_dst_path))
            dst_name = os.path.basename(host_dst_path)
            cmd = [self.docker_bin, "cp", src, dst_name]
            r = subprocess.run(cmd, cwd=dst_dir, capture_output=True, text=True, timeout=20)
            return r.returncode == 0
        except Exception:
            return False

    def cleanup(self):
        if self._created:
            try:
                subprocess.run([self.docker_bin, "rm", "-f", self.container_name],
                               capture_output=True, timeout=15)
            except Exception:
                pass
            self._created = False


def create_runner(workdir: str, lang: str = "python", prefer_docker: bool = True):
    """Ortama göre en uygun Runner'ı oluşturur."""
    if prefer_docker and is_docker_available():
        return DockerRunner(host_workdir=workdir, lang=lang)
    return LocalRunner(workdir=workdir)
