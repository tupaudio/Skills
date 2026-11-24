"""Leitura real do relogio monotonico por plataforma (ACH-B7-R18-004).

Nao permite simulacao nem declaracao manual de clock_source divergente do SO.
"""
import ctypes
import os
import platform
import time
import uuid
from dataclasses import dataclass


class PlatformClockError(Exception):
    """Erro explicito de relogio monotonico de plataforma."""


def read_linux_monotonic_raw_ns() -> int:
    """Usa CLOCK_MONOTONIC_RAW real. Rejeita plataformas sem esse relogio."""
    if platform.system() != "Linux" or not hasattr(time, "CLOCK_MONOTONIC_RAW"):
        raise PlatformClockError("CLOCK_MONOTONIC_RAW disponivel apenas em Linux >= 5.6")
    ns = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
    if not isinstance(ns, int) or ns < 0:
        raise PlatformClockError("Valor invalido de CLOCK_MONOTONIC_RAW")
    return ns


def read_windows_qpc_ns() -> int:
    """Usa QueryPerformanceCounter e QueryPerformanceFrequency com aritmetica inteira exata."""
    if platform.system() != "Windows":
        raise PlatformClockError("QPC disponivel apenas em Windows")
    freq = ctypes.c_int64()
    ticks = ctypes.c_int64()
    if ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(freq)) == 0 or freq.value <= 0:
        raise PlatformClockError("QueryPerformanceFrequency invalida ou zero")
    if ctypes.windll.kernel32.QueryPerformanceCounter(ctypes.byref(ticks)) == 0 or ticks.value < 0:
        raise PlatformClockError("QueryPerformanceCounter invalido")
    return (ticks.value * 1_000_000_000) // freq.value


def read_platform_monotonic_ns() -> tuple[str, int]:
    """Seleciona estritamente a fonte real do SO em execucao."""
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


def create_runtime_clock_context(store_epoch: str) -> RuntimeClockContext:
    source, now_ns = read_platform_monotonic_ns()
    return RuntimeClockContext(
        clock_context_id=str(uuid.uuid4()),
        clock_source=source,
        created_ns=now_ns,
        store_epoch=store_epoch,
        pid=os.getpid(),
    )


def validate_runtime_clock_context(ctx: RuntimeClockContext, expected_store_epoch: str) -> int:
    source, now_ns = read_platform_monotonic_ns()
    if ctx.clock_source != source:
        raise PlatformClockError("Origem de relogio incompativel com o SO")
    if ctx.store_epoch != expected_store_epoch:
        raise PlatformClockError("store_epoch alterado; contexto invalidado")
    if ctx.pid != os.getpid():
        raise PlatformClockError("Reinicializacao de processo detectada (PID divergente)")
    if now_ns < ctx.created_ns:
        raise PlatformClockError("Regressao monotonica detectada")
    return now_ns
