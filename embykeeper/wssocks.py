import asyncio
import hashlib
import os
import platform
import subprocess
import httpx
from pathlib import Path
import stat
from typing import Optional

from loguru import logger

from .schema import ProxyConfig
from .utils import get_proxy_str
from .config import config


# 各平台可执行文件的 magic 头, 用于在未提供 SHA-256 时做最低限度的二进制完整性校验
# 防御场景: HTTPS MITM 替换、GitHub 404 HTML 错误页、截断下载
_BINARY_MAGIC = {
    "Linux": (b"\x7fELF",),
    "Darwin": (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"),
    "Windows": (b"MZ",),
}


class WSSocks:
    BASE_URL = "https://github.com/zetxtech/wssocks/releases/download/v1.4.2"

    PLATFORM_MAPPING = {
        "Linux": {
            "x86_64": "wssocks-linux-amd64",
            "aarch64": "wssocks-linux-arm64",
        },
        "Darwin": {
            "x86_64": "wssocks-darwin-amd64",
            "arm64": "wssocks-darwin-arm64",
        },
        "Windows": {
            "AMD64": "wssocks-windows-amd64.exe",
        },
    }

    def __init__(self, proxy=None):
        """Initialize WSSocks handler

        Args:
            cache_dir: Directory to store downloaded files. Defaults to ~/.cache/embykeeper
        """
        self.system = platform.system()
        self.machine = platform.machine()
        self.process: Optional[subprocess.Popen] = None
        self._proxy = proxy

    @property
    def proxy_str(self):
        return get_proxy_str(self._proxy or config.proxy)

    @property
    def executable_path(self) -> Path:
        """Get path to the executable"""
        exe_name = "wssocks.exe" if self.system == "Windows" else "wssocks"
        return config.basedir / exe_name

    def get_download_url(self) -> str:
        """Generate download URL based on current platform"""
        try:
            filename = self.PLATFORM_MAPPING[self.system][self.machine]
            return f"{self.BASE_URL}/{filename}"
        except KeyError:
            raise RuntimeError(f"Unsupported platform: {self.system} {self.machine}")

    async def download(self) -> None:
        """Download wssocks binary asynchronously, with integrity verification."""

        url = self.get_download_url()
        temp_path = config.basedir / self.PLATFORM_MAPPING[self.system][self.machine]

        async with httpx.AsyncClient(proxy=self.proxy_str, http2=True, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content

        # 1) 完整性校验: 若 EK_WSSOCKS_SHA256 已配置, 必须严格匹配
        expected_sha = os.environ.get("EK_WSSOCKS_SHA256", "").strip().lower()
        actual_sha = hashlib.sha256(content).hexdigest()
        if expected_sha:
            if actual_sha != expected_sha:
                raise RuntimeError(
                    f"wssocks 二进制 SHA-256 校验失败: expected={expected_sha} actual={actual_sha}"
                )
            logger.debug(f"wssocks 二进制 SHA-256 校验通过: {actual_sha}")
        else:
            # 2) 兜底: 至少验证 magic 头, 防止把 HTML 错误页或损坏文件当二进制执行
            magic_options = _BINARY_MAGIC.get(self.system, ())
            if magic_options and not any(content.startswith(m) for m in magic_options):
                raise RuntimeError(
                    f"下载的 wssocks 不是有效的 {self.system} 可执行文件 (magic 校验失败). "
                    f"SHA-256={actual_sha}. 可设置 EK_WSSOCKS_SHA256 环境变量做精确校验."
                )
            logger.debug(f"wssocks 已下载, SHA-256={actual_sha} (未启用精确校验)")

        with open(temp_path, "wb") as f:
            f.write(content)

        temp_path.rename(self.executable_path)

        if self.system != "Windows":
            self.executable_path.chmod(self.executable_path.stat().st_mode | stat.S_IEXEC)

    async def ensure_binary(self) -> None:
        """Ensure binary exists and download if necessary"""
        if not self.executable_path.exists():
            await self.download()

    async def execute(self, *args) -> subprocess.Popen:
        """Execute wssocks with given arguments and return Popen object"""
        await self.ensure_binary()
        return subprocess.Popen(
            [str(self.executable_path), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    async def start(self, host: str, token: str, connector_token: str, proxy: ProxyConfig = None) -> bool:
        """Start wssocks client server

        Args:
            host: Server address with port
            token: Authentication token
            connector_token: Connector token
            proxy_dict: Proxy configuration dictionary containing scheme, hostname, port, and optional username/password
        """
        if self.process and self.process.poll() is None:
            raise RuntimeError("WSSocks is already running")

        args = ["client", "-u", host, "-r", "-t", token, "-T", "1", "-c", connector_token, "-d", "-E"]
        proxy_str = get_proxy_str(proxy)
        if proxy_str:
            args.extend(["-x", proxy_str])

        self.process = await self.execute(*args)

        await asyncio.sleep(3)
        if self.process.poll() is not None:
            stdout, stderr = self.process.communicate()
            return stderr.decode()
        return None

    def stop(self) -> None:
        """Stop wssocks server if running"""
        if self.process:
            if self.process.poll() is None:  # Process is still running
                self.process.terminate()  # Try graceful shutdown first
                try:
                    self.process.wait(timeout=5)  # Wait up to 5 seconds
                except subprocess.TimeoutExpired:
                    self.process.kill()  # Force kill if not terminated
            self.process = None
