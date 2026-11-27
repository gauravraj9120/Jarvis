"""Cross-platform system telemetry, using Win32 APIs on Windows."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import os
import platform
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import psutil

_STATE_LOCK = threading.Lock()
_PREV_CPU: tuple[int, int, int] | None = None
_PREV_NET: tuple[int, int, float] | None = None


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", w.DWORD),
        ("dwMemoryLoad", w.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


class _MIB_IFROW(ctypes.Structure):
    _fields_ = [
        ("wszName", ctypes.c_wchar * 256),
        ("dwIndex", w.DWORD),
        ("dwType", w.DWORD),
        ("dwMtu", w.DWORD),
        ("dwSpeed", w.DWORD),
        ("dwPhysAddrLen", w.DWORD),
        ("bPhysAddr", ctypes.c_ubyte * 8),
        ("dwAdminStatus", w.DWORD),
        ("dwOperStatus", w.DWORD),
        ("dwLastChange", w.DWORD),
        ("dwInOctets", w.DWORD),
        ("dwInUcastPkts", w.DWORD),
        ("dwInNUcastPkts", w.DWORD),
        ("dwInDiscards", w.DWORD),
        ("dwInErrors", w.DWORD),
        ("dwInUnknownProtos", w.DWORD),
        ("dwOutOctets", w.DWORD),
        ("dwOutUcastPkts", w.DWORD),
        ("dwOutNUcastPkts", w.DWORD),
        ("dwOutDiscards", w.DWORD),
        ("dwOutErrors", w.DWORD),
        ("dwOutQLen", w.DWORD),
        ("dwDescrLen", w.DWORD),
        ("bDescr", ctypes.c_ubyte * 256),
    ]


def _get_cpu_percent() -> float:
    if os.name != "nt":
        return round(psutil.cpu_percent(interval=0.1), 1)

    global _PREV_CPU
    idle, kernel, user = ctypes.c_uint64(), ctypes.c_uint64(), ctypes.c_uint64()
    if not ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
    ):
        return 0.0

    cur = (idle.value, kernel.value, user.value)
    with _STATE_LOCK:
        prev = _PREV_CPU
        _PREV_CPU = cur

    if prev is None:
        time.sleep(0.2)
        idle2, kernel2, user2 = ctypes.c_uint64(), ctypes.c_uint64(), ctypes.c_uint64()
        ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle2), ctypes.byref(kernel2), ctypes.byref(user2)
        )
        prev = cur
        cur = (idle2.value, kernel2.value, user2.value)
        with _STATE_LOCK:
            _PREV_CPU = cur

    d_idle = cur[0] - prev[0]
    d_kernel = cur[1] - prev[1]
    d_user = cur[2] - prev[2]
    total = d_kernel + d_user
    if total <= 0:
        return 0.0
    busy = max(0, total - d_idle)
    return round(min(100.0, (busy / total) * 100.0), 1)


def _get_memory_info() -> dict[str, Any]:
    if os.name != "nt":
        mem = psutil.virtual_memory()
        return {
            "percent": round(float(mem.percent), 1),
            "used_gb": round(mem.used / (1024**3), 1),
            "total_gb": round(mem.total / (1024**3), 1),
        }

    mem = _MEMORYSTATUSEX()
    mem.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
        return {"percent": 0.0, "used_gb": 0.0, "total_gb": 0.0}
    total_gb = mem.ullTotalPhys / (1024**3)
    avail_gb = mem.ullAvailPhys / (1024**3)
    used_gb = max(0.0, total_gb - avail_gb)
    return {
        "percent": round(float(mem.dwMemoryLoad), 1),
        "used_gb": round(used_gb, 1),
        "total_gb": round(total_gb, 1),
    }


def _get_disk_info() -> dict[str, Any]:
    if os.name != "nt":
        root = Path(__file__).resolve().anchor or "/"
        usage = shutil.disk_usage(root)
        pct = (usage.used / usage.total) * 100.0 if usage.total else 0.0
        return {
            "drive": root,
            "percent": round(pct, 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "total_gb": round(usage.total / (1024**3), 1),
        }

    drive = Path(__file__).resolve().drive or "C:"
    usage = shutil.disk_usage(f"{drive}\\")
    pct = (usage.used / usage.total) * 100.0 if usage.total else 0.0
    return {
        "drive": drive,
        "percent": round(pct, 1),
        "used_gb": round(usage.used / (1024**3), 1),
        "total_gb": round(usage.total / (1024**3), 1),
    }


def _read_network_octets() -> tuple[int, int]:
    if os.name != "nt":
        counters = psutil.net_io_counters()
        return (counters.bytes_recv, counters.bytes_sent) if counters else (0, 0)

    sz = w.DWORD(0)
    ctypes.windll.iphlpapi.GetIfTable(None, ctypes.byref(sz), False)
    if sz.value == 0:
        return (0, 0)
    buf = (ctypes.c_ubyte * sz.value)()
    res = ctypes.windll.iphlpapi.GetIfTable(buf, ctypes.byref(sz), False)
    if res != 0:
        return (0, 0)

    num = ctypes.c_uint32.from_buffer(buf, 0).value
    max_rows = (sz.value - 4) // ctypes.sizeof(_MIB_IFROW)
    count = min(num, max_rows)
    rows = (_MIB_IFROW * count).from_buffer(buf, 4)

    total_in = 0
    total_out = 0
    seen_pairs: set[tuple[int, int]] = set()
    filter_markers = ("-WFP", "-QoS", "Filter", "Scheduler", "VirtualBox NDIS")

    for row in rows:
        if row.dwType == 24:  # software loopback
            continue
        descr = bytes(row.bDescr[: min(row.dwDescrLen, 256)]).decode("ascii", "ignore")
        if any(marker in descr for marker in filter_markers):
            continue
        if row.dwInOctets == 0 and row.dwOutOctets == 0:
            continue
        pair = (int(row.dwInOctets), int(row.dwOutOctets))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        total_in += pair[0]
        total_out += pair[1]

    return (total_in, total_out)


def _get_network_speed() -> dict[str, Any]:
    global _PREV_NET
    now = time.monotonic()
    rx_bytes, tx_bytes = _read_network_octets()

    with _STATE_LOCK:
        prev = _PREV_NET
        _PREV_NET = (rx_bytes, tx_bytes, now)

    if prev is None:
        return {"download_mbps": 0.0, "upload_mbps": 0.0, "rx_bytes": rx_bytes, "tx_bytes": tx_bytes}

    dt = max(0.1, now - prev[2])
    # Handle 32-bit DWORD counter wrap gracefully
    d_rx = rx_bytes - prev[0] if rx_bytes >= prev[0] else 0
    d_tx = tx_bytes - prev[1] if tx_bytes >= prev[1] else 0

    down_mbps = (d_rx * 8.0) / (dt * 1_000_000.0)
    up_mbps = (d_tx * 8.0) / (dt * 1_000_000.0)
    return {
        "download_mbps": round(down_mbps, 2),
        "upload_mbps": round(up_mbps, 2),
        "rx_bytes": rx_bytes,
        "tx_bytes": tx_bytes,
    }


def _get_uptime_seconds() -> int:
    if os.name != "nt":
        return max(0, int(time.time() - psutil.boot_time()))

    ms = ctypes.windll.kernel32.GetTickCount64()
    return int(ms // 1000)


def get_system_snapshot() -> dict[str, Any]:
    """Return a single lightweight telemetry snapshot for the HUD."""
    cpu = _get_cpu_percent()
    mem = _get_memory_info()
    disk = _get_disk_info()
    net = _get_network_speed()
    uptime_sec = _get_uptime_seconds()
    hours, rem = divmod(uptime_sec, 3600)
    minutes, _ = divmod(rem, 60)

    return {
        "cpu": {"percent": cpu, "cores": os.cpu_count() or 1},
        "ram": mem,
        "disk": disk,
        "network": net,
        "host": {
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()}",
            "arch": platform.machine(),
            "python": platform.python_version(),
            "uptime": f"{hours}h {minutes}m",
        },
    }


def get_active_connections(limit: int = 30) -> list[dict[str, str]]:
    """Return active TCP connections using the platform's available APIs."""
    if os.name != "nt":
        try:
            connections = psutil.net_connections(kind="tcp")
        except psutil.Error:
            return []

        rows: list[dict[str, str]] = []
        for connection in connections:
            local = (
                f"{connection.laddr.ip}:{connection.laddr.port}"
                if connection.laddr
                else ""
            )
            remote = (
                f"{connection.raddr.ip}:{connection.raddr.port}"
                if connection.raddr
                else ""
            )
            rows.append(
                {
                    "proto": "TCP",
                    "local": local,
                    "remote": remote,
                    "state": connection.status,
                    "pid": str(connection.pid or ""),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return []

    rows: list[dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "TCP":
            rows.append(
                {
                    "proto": parts[0],
                    "local": parts[1],
                    "remote": parts[2],
                    "state": parts[3],
                    "pid": parts[4],
                }
            )
            if len(rows) >= limit:
                break
    return rows


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", w.DWORD),
        ("cntUsage", w.DWORD),
        ("th32ProcessID", w.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", w.DWORD),
        ("cntThreads", w.DWORD),
        ("th32ParentProcessID", w.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", w.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", w.DWORD),
        ("PageFaultCount", w.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def get_top_processes(limit: int = 18) -> list[dict[str, Any]]:
    """Return running processes sorted by memory usage."""
    if os.name != "nt":
        processes: list[dict[str, Any]] = []
        for proc in psutil.process_iter(
            attrs=["pid", "name", "num_threads", "memory_info"]
        ):
            try:
                info = proc.info
                memory = info["memory_info"]
                processes.append(
                    {
                        "name": info["name"] or "Unknown",
                        "pid": str(info["pid"]),
                        "threads": info["num_threads"] or 0,
                        "memory_mb": round(memory.rss / (1024.0 * 1024.0), 1)
                        if memory
                        else 0.0,
                    }
                )
            except (psutil.Error, OSError):
                continue
        processes.sort(key=lambda proc: proc["memory_mb"], reverse=True)
        return processes[:limit]

    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_VM_READ = 0x0010

    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == ctypes.c_void_p(-1).value:
        return []

    procs: list[dict[str, Any]] = []
    entry = _PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)

    try:
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            pid = int(entry.th32ProcessID)
            mem_mb = 0.0
            if pid > 0:
                hproc = kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid
                )
                if not hproc:
                    hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if hproc:
                    pmc = _PROCESS_MEMORY_COUNTERS()
                    pmc.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
                    if psapi.GetProcessMemoryInfo(hproc, ctypes.byref(pmc), pmc.cb):
                        mem_mb = round(pmc.WorkingSetSize / (1024.0 * 1024.0), 1)
                    kernel32.CloseHandle(hproc)
            procs.append(
                {
                    "name": entry.szExeFile,
                    "pid": str(pid),
                    "threads": int(entry.cntThreads),
                    "memory_mb": mem_mb,
                }
            )
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)

    procs.sort(key=lambda p: p["memory_mb"], reverse=True)
    return procs[:limit]
