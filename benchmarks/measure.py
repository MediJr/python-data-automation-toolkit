"""Wall-clock time and peak memory of a command and all its child processes (Windows only).

The command is started suspended, assigned to a fresh Job Object, then resumed, so every
child process belongs to the job. Time is measured with ``time.perf_counter`` from just
before process creation to exit. Memory is the kernel's ``PeakJobMemoryUsed`` (peak
committed private memory of all processes in the job): no sampling is involved.

Method adapted (copied, not imported: ADR-0008) from the benchmark of service 1.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time

if sys.platform != "win32":
    raise SystemExit("measure.py uses the Windows Job Object API and only runs on Windows.")

from ctypes import wintypes as wt  # noqa: E402 - Windows-only module

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
kernel32.CreateJobObjectW.restype = wt.HANDLE
CREATE_SUSPENDED = 0x00000004
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ("r", "w", "o", "rt", "wt", "ot")]


class _BasicLimit(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wt.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wt.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wt.DWORD),
        ("SchedulingClass", wt.DWORD),
    ]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("Basic", _BasicLimit),
        ("Io", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _check(ok: object, what: str) -> None:
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error(), what)


def run_measured(cmd: list[str], cwd: str | None = None, env: dict[str, str] | None = None) -> dict:
    job = kernel32.CreateJobObjectW(None, None)
    _check(job, "CreateJobObject")
    try:
        start = time.perf_counter()
        process = subprocess.Popen(  # noqa: S603 - fixed argument list, no shell
            cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_SUSPENDED
        )
        handle = wt.HANDLE(int(process._handle))
        _check(kernel32.AssignProcessToJobObject(job, handle), "AssignProcessToJobObject")
        ntdll.NtResumeProcess(handle)
        stdout, stderr = process.communicate()
        wall = time.perf_counter() - start
        info = _ExtendedLimit()
        _check(
            kernel32.QueryInformationJobObject(
                job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info), None
            ),
            "QueryInformationJobObject",
        )
    finally:
        kernel32.CloseHandle(wt.HANDLE(job))
    return {
        "exit_code": process.returncode,
        "wall_seconds": wall,
        "peak_job_commit_bytes": info.PeakJobMemoryUsed,
        "stdout": stdout.decode("utf-8", "replace"),
        "stderr": stderr.decode("utf-8", "replace"),
    }


if __name__ == "__main__":  # calibration: a process that allocates a known amount of memory
    for mib in (0, 200):
        code = f"b = bytearray({mib} * 1024 * 1024); b[::4096] = b'x' * len(b[::4096])"
        result = run_measured([sys.executable, "-c", code])
        print(f"allocated {mib} MiB -> peak commit {result['peak_job_commit_bytes'] / 2**20:.1f} MiB")
