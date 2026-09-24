"""Jaga PC tetap bangun selama workflow malam (SetThreadExecutionState).

Tanpa mutasi setting sistem — state hanya hidup selama proses ini jalan.
Matikan = kill proses (atau task selesai) → Windows kembali ke timer tidur
semula. Heartbeat tiap menit ke stdout.
"""
import ctypes
import sys
import time

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040


def main() -> int:
    ctypes.windll.kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
    print("[keep-awake] AKTIF — sistem tidak akan sleep (display boleh mati)", flush=True)
    try:
        while True:
            time.sleep(60)
            # perbarui state tiap menit (tahan terhadap reset oleh proses lain)
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
            print(f"[keep-awake] heartbeat {time.strftime('%H:%M:%S')}", flush=True)
    except KeyboardInterrupt:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        print("[keep-awake] dilepas", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
