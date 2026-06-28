from __future__ import annotations

import socket
import sys


def can_bind(family: socket.AddressFamily, host: str, port: int) -> bool | None:
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except PermissionError:
            return None
        except OSError:
            return False
    return True


def is_free(port: int) -> bool:
    ipv4_result = can_bind(socket.AF_INET, "0.0.0.0", port)
    if ipv4_result is False:
        return False

    if socket.has_ipv6:
        ipv6_result = can_bind(socket.AF_INET6, "::", port)
        if ipv6_result is False:
            return False

    return True


def main() -> int:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    for port in range(start, min(65536, start + max(1, limit))):
        if is_free(port):
            print(port)
            return 0

    end = min(65535, start + max(1, limit) - 1)
    print(f"No free port found from {start} to {end}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
