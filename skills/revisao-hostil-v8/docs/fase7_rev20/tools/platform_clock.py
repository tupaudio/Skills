"""Leitura real do relogio monotonico e ciclo de vida com boot_id (ACH-B7-R19-005)."""
import ctypes
import hashlib
import os
import platform
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


class PlatformClockError(Exception):
    """Erro explicito de relogio monotonico de plataforma."""


def _parse_linux_kernel_version(rel: str) -> tuple[int, int]:
    parts = rel.split("-")[0].split(".")
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise PlatformClockError(f"Versao de kernel Linux invalida: {rel!r}")
    return int(parts[0]), int(parts[1])


def get_system_boot_id() -> str:
    system = platform.system()
    if system == "Linux":
        p = Path("/proc/sys/kernel/random/boot_id")
        if not p.exists():
            raise PlatformClockError("/proc/sys/kernel/random/boot_id ausente")
        bid = p.read_text(encoding="utf-8").strip().lower()
        if len(bid) != 36:
            raise PlatformClockError(f"boot_id Linux invalido: {bid!r}")
        return f"linux-boot:{bid}"
    if system == "Windows":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        uptime_ms = ctypes.windll.kernel32.GetTickCount64()
        boot_epoch_sec = int(time.time()) - int(uptime_ms // 1000)
        digest = hashlib.sha256(f"{machine_guid}:{boot_epoch_sec // 60}".encode("utf-8")).hexdigest()[:32]
        return f"windows-boot:{digest}"
    raise PlatformClockError(f"Plataforma sem boot_id homologado: {system}")


def read_linux_monotonic_raw_ns() -> int:
    if platform.system() != "Linux" or not hasattr(time, "CLOCK_MONOTONIC_RAW"):
        raise PlatformClockError("CLOCK_MONOTONIC_RAW disponivel apenas em Linux >= 5.6")
    maj, minor = _parse_linux_kernel_version(platform.release())
    if (maj, minor) < (5, 6):
        raise PlatformClockError(f"Kernel Linux {maj}.{minor} abaixo do minimo 5.6")
    ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
    if not isinstance(ns, int) or ns < 0:
        raise PlatformClockError("Valor invalido de CLOCK_MONOTONIC_RAW")
    return ns


def read_windows_qpc_ns() -> int:
    if platform.system() != "Windows":
        raise PlatformClockError("QPC disponivel apenas em Windows")
    freq, ticks = ctypes.c_int64(), ctypes.c_int64()
    if ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(freq)) == 0 or freq.value <= 0:
        raise PlatformClockError("QueryPerformanceFrequency invalida ou zero")
    if ctypes.windll.kernel32.QueryPerformanceCounter(ctypes.byref(ticks)) == 0 or ticks.value < 0:
        raise PlatformClockError("QueryPerformanceCounter invalido")
    return (ticks.value * 1_000_000_000) // freq.value


def read_platform_monotonic_ns() -> tuple[str, int]:
    system = platform.system()
    if system == "Linux":
        return "linux_clock_monotonic_raw", read_linux_monotonic_raw_ns()
    if system == "Windows":
        return "windows_query_performance_counter", read_windows_qpc_ns()
    raise PlatformClockError(f"Plataforma sem suporte monotonico homologado: {system}")


@dataclass(frozen=True)
class RuntimeClockContext:
    clock_context_id: str
    clock_source: str
    created_ns: int
    store_epoch: str
    pid: int
    boot_id: str


def create_runtime_clock_context(store_epoch: str) -> RuntimeClockContext:
    source, now_ns = read_platform_monotonic_ns()
    return RuntimeClockContext(
        clock_context_id=str(uuid.uuid4()),
        clock_source=source,
        created_ns=now_ns,
        store_epoch=store_epoch,
        pid=os.getpid(),
        boot_id=get_system_boot_id(),
    )


def validate_runtime_clock_context(
    ctx: RuntimeClockContext,
    expected_store_epoch: str,
    expected_context_id: str | None = None,
    current_pid: int | None = None,
    current_boot_id: str | None = None,
) -> int:
    source, now_ns = read_platform_monotonic_ns()
    if ctx.clock_source != source:
        raise PlatformClockError("Origem de relogio incompativel com o SO")
    if ctx.store_epoch != expected_store_epoch:
        raise PlatformClockError("store_epoch alterado; contexto invalidado")
    if expected_context_id is not None and ctx.clock_context_id != expected_context_id:
        raise PlatformClockError("UUID do contexto diverge do recibo")
    actual_pid = os.getpid() if current_pid is None else current_pid
    if ctx.pid != actual_pid:
        raise PlatformClockError("Reinicializacao de processo detectada (PID divergente)")
    actual_boot = get_system_boot_id() if current_boot_id is None else current_boot_id
    if ctx.boot_id != actual_boot:
        raise PlatformClockError("Reinicializacao do sistema detectada (boot_id divergente)")
    if now_ns < ctx.created_ns:
        raise PlatformClockError("Regressao monotonica detectada")
    return now_ns
