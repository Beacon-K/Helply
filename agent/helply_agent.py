#!/usr/bin/env python3
"""Helply monitoring agent - reports this server's health to Helply every few seconds.

It ONLY SENDS readings (CPU, memory, swap, disk, network, load, processes, uptime) over HTTPS.
It opens no ports, accepts no commands and changes nothing on the machine.

Settings come from environment variables or a config file (KEY=value lines):
    HELPLY_URL        https://helply.example.com
    HELPLY_TOKEN      the agent token shown once in Helply
    HELPLY_INTERVAL   seconds between reports (default 10, minimum 5)
Config file: /etc/helply-agent.conf (Linux) or C:\\ProgramData\\HelplyAgent\\agent.conf (Windows),
or pass --config PATH. Requires Python 3.8+ and psutil.

    python3 helply_agent.py --once     # print one report and send it, to test the setup
"""
import argparse
import json
import os
import platform
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request

VERSION = "1.1.0"
DEFAULT_CONFIG = (r"C:\ProgramData\HelplyAgent\agent.conf" if os.name == "nt" else "/etc/helply-agent.conf")
# Virtual interfaces whose traffic is counted twice or is purely local.
SKIP_NICS = ("lo", "docker", "veth", "br-", "virbr", "vnet", "cni", "flannel", "cali", "tun", "tap", "zt", "tailscale",
             "wg", "Loopback", "isatap", "Teredo", "vEthernet")
SKIP_FS = {"tmpfs", "devtmpfs", "squashfs", "overlay", "aufs", "proc", "sysfs", "cgroup", "cgroup2", "devpts",
           "nsfs", "tracefs", "autofs", "ramfs", "iso9660", "fuse.lxcfs", ""}

try:
    import psutil
except ImportError:  # pragma: no cover - explained to the user instead of a traceback
    sys.exit("The Helply agent needs psutil: run  python3 -m pip install psutil  (or apt install python3-psutil).")


def log(message):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def load_config(path):
    config = {}
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip().upper()] = value.strip().strip('"').strip("'")
    for key in ("HELPLY_URL", "HELPLY_TOKEN", "HELPLY_INTERVAL"):
        if os.environ.get(key):
            config[key] = os.environ[key]
    return config


def os_name():
    if os.name == "nt":
        release, version, _, _ = platform.win32_ver()
        edition = platform.win32_edition() if hasattr(platform, "win32_edition") else ""
        return " ".join(x for x in ["Windows", release, edition, f"({version})" if version else ""] if x)
    try:
        with open("/etc/os-release", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return f"{platform.system()} {platform.release()}"


def cpu_model():
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


# --- cloud detection ---------------------------------------------------------------------------
# Read once at start-up so Helply can fill in provider, region and machine size by itself.
# Only the hardware vendor strings and the provider's own link-local metadata service are read.
VENDOR_HINTS = [  # (substring of vendor/product/asset tag, provider)
    ("oraclecloud", "oracle"), ("amazon", "aws"), ("ec2", "aws"), ("google", "gcp"),
    ("digitalocean", "digitalocean"), ("hetzner", "hetzner"), ("vultr", "vultr"), ("linode", "linode"),
    ("akamai", "linode"), ("alibaba", "alibaba"), ("tencent", "tencent"), ("ovh", "ovh"),
    ("microsoft corporation", "azure"),  # Hyper-V too: confirmed through Azure's metadata below
]


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def hardware_vendor():
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS")
            parts = [str(winreg.QueryValueEx(key, name)[0]) for name in ("SystemManufacturer", "SystemProductName")]
            return " ".join(p for p in parts if p)
        except OSError:
            return ""
    names = ("sys_vendor", "product_name", "chassis_asset_tag", "bios_vendor")
    return " ".join(v for v in (_read(f"/sys/class/dmi/id/{n}") for n in names) if v)


def _metadata(url, headers=None, method="GET", timeout=1.5):
    request = urllib.request.Request(url, headers=headers or {}, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never via a proxy
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.read(65536).decode("utf-8", "replace").strip()
    except Exception:
        return ""


def cloud_info():
    vendor = hardware_vendor()
    lowered = vendor.lower()
    provider = next((p for hint, p in VENDOR_HINTS if hint in lowered), "")
    region = instance_type = ""
    base = "http://169.254.169.254"
    try:
        if provider == "oracle":
            data = json.loads(_metadata(base + "/opc/v2/instance/", {"Authorization": "Bearer Oracle"}) or "{}")
            region, instance_type = data.get("canonicalRegionName", ""), data.get("shape", "")
        elif provider == "aws":
            token = _metadata(base + "/latest/api/token", {"X-aws-ec2-metadata-token-ttl-seconds": "60"}, "PUT")
            auth = {"X-aws-ec2-metadata-token": token} if token else {}
            region = _metadata(base + "/latest/meta-data/placement/region", auth)
            instance_type = _metadata(base + "/latest/meta-data/instance-type", auth)
        elif provider == "azure":
            data = json.loads(_metadata(base + "/metadata/instance/compute?api-version=2021-02-01",
                                        {"Metadata": "true"}) or "{}")
            if data:
                region, instance_type = data.get("location", ""), data.get("vmSize", "")
            else:
                provider = ""  # plain Hyper-V, not Azure
        elif provider == "gcp":
            google = {"Metadata-Flavor": "Google"}
            zone = _metadata("http://metadata.google.internal/computeMetadata/v1/instance/zone", google)
            region = zone.rsplit("/", 1)[-1]
            instance_type = _metadata("http://metadata.google.internal/computeMetadata/v1/instance/machine-type",
                                      google).rsplit("/", 1)[-1]
        elif provider == "digitalocean":
            region = _metadata(base + "/metadata/v1/region")
        elif provider == "hetzner":
            region = _metadata(base + "/hetzner/v1/metadata/availability-zone")
    except ValueError:
        pass
    clean = lambda text: text if text and len(text) < 80 and "<" not in text else ""
    return {"vendor": vendor[:160], "provider": provider, "region": clean(region), "instance_type": clean(instance_type)}


def host_info():
    info = {
        "hostname": socket.gethostname(),
        "os_family": "windows" if os.name == "nt" else platform.system().lower(),
        "os_name": os_name(),
        "arch": platform.machine(),
        "cpu_model": cpu_model(),
        "cpu_cores": psutil.cpu_count(logical=True),
    }
    info.update(cloud_info())
    return info


def disk_usage():
    """Used/total over real local file systems, each device counted once."""
    used = total = 0
    seen = set()
    for part in psutil.disk_partitions(all=False):
        if part.fstype.lower() in SKIP_FS or "cdrom" in part.opts or part.device in seen:
            continue
        if os.name != "nt" and part.mountpoint.startswith(("/snap", "/boot/efi", "/var/lib/docker")):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        seen.add(part.device)
        used += usage.used
        total += usage.total
    return {"used": used, "total": total}


def net_totals():
    rx = tx = 0
    for name, counters in psutil.net_io_counters(pernic=True).items():
        if name.startswith(SKIP_NICS):
            continue
        rx += counters.bytes_recv
        tx += counters.bytes_sent
    return rx, tx


class Collector:
    def __init__(self):
        self.host = host_info()
        self.host_sent_at = 0.0
        psutil.cpu_percent(interval=None)  # the first call only starts the measurement
        self.last_net = net_totals()
        self.last_time = time.monotonic()

    def report(self):
        now = time.monotonic()
        elapsed = max(now - self.last_time, 0.001)
        rx, tx = net_totals()
        # Counters can reset (interface restart): never report a negative rate.
        rx_rate = max(rx - self.last_net[0], 0) / elapsed
        tx_rate = max(tx - self.last_net[1], 0) / elapsed
        self.last_net, self.last_time = (rx, tx), now

        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        try:
            load = list(psutil.getloadavg())
        except (AttributeError, OSError):
            load = None
        report = {
            "version": VERSION,
            "cpu": psutil.cpu_percent(interval=None),
            "mem": {"used": memory.total - memory.available, "total": memory.total},
            "swap": {"used": swap.used, "total": swap.total},
            "disk": disk_usage(),
            "net": {"rx_rate": rx_rate, "tx_rate": tx_rate, "rx_total": rx, "tx_total": tx},
            "load": load,
            "processes": len(psutil.pids()),
            "uptime": int(time.time() - psutil.boot_time()),
        }
        if time.time() - self.host_sent_at > 600:  # static details every 10 minutes
            report["host"] = self.host
        return report


def send(url, token, report, timeout=10):
    request = urllib.request.Request(
        url, data=json.dumps(report).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}",
                 "User-Agent": f"helply-agent/{VERSION}"},
    )
    context = ssl.create_default_context()  # certificates are always verified
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return json.loads(response.read() or b"{}")


def main():
    parser = argparse.ArgumentParser(description="Helply monitoring agent (read-only).")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--once", action="store_true", help="Send one report, print it and exit.")
    args = parser.parse_args()

    config = load_config(args.config)
    base, token = config.get("HELPLY_URL", "").rstrip("/"), config.get("HELPLY_TOKEN", "")
    if not base or not token:
        sys.exit(f"Set HELPLY_URL and HELPLY_TOKEN (in {args.config} or the environment).")
    if not base.startswith("https://") and not base.startswith(("http://127.0.0.1", "http://localhost")):
        sys.exit("HELPLY_URL must start with https:// so the token and readings are encrypted.")
    try:
        interval = max(5.0, float(config.get("HELPLY_INTERVAL", "10")))
    except ValueError:
        interval = 10.0
    url = base + "/monitoring/api/report/"

    collector = Collector()
    if args.once:
        time.sleep(1)
        report = collector.report()
        print(json.dumps(report, indent=2))
        print(send(url, token, report))
        return

    log(f"Helply agent {VERSION} reporting to {base} every {interval:.0f}s")
    failures = 0
    while True:
        started = time.monotonic()
        try:
            report = collector.report()
            send(url, token, report)
            if "host" in report:
                collector.host_sent_at = time.time()
            if failures:
                log("Connection restored.")
            failures = 0
        except urllib.error.HTTPError as error:
            failures += 1
            if error.code == 401:
                log("Helply rejected the token (revoked or wrong). Update HELPLY_TOKEN; retrying in 5 minutes.")
                time.sleep(300)
                continue
            log(f"Helply answered HTTP {error.code}; will retry.")
        except Exception as error:  # network trouble: keep trying, but back off
            failures += 1
            if failures in (1, 5) or failures % 60 == 0:
                log(f"Cannot reach Helply ({error.__class__.__name__}: {error}); will keep retrying.")
        delay = interval if failures < 3 else min(interval * failures, 120)
        time.sleep(max(delay - (time.monotonic() - started), 1))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
