"""配置管理模块：从config.ini文件读取配置，支持INI格式便于手动修改"""

import configparser
import os
from pathlib import Path


class ConfigManager:
    """配置管理器：从项目根目录的config.ini文件读取配置"""

    def __init__(self, config_file: str | None = None):
        """
        初始化配置管理器

        参数:
            config_file: 配置文件路径，默认为项目根目录下的config.ini
        """
        if config_file is None:
            # 项目根目录下的config.ini
            config_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config.ini"
            )
        self._config_file = config_file
        self._parser = configparser.ConfigParser()
        self.load()

    def load(self):
        """从config.ini加载配置"""
        if os.path.exists(self._config_file):
            self._parser.read(self._config_file, encoding="utf-8")
        else:
            raise FileNotFoundError(f"配置文件不存在: {self._config_file}")

    def save(self):
        """保存配置到config.ini"""
        with open(self._config_file, "w", encoding="utf-8") as f:
            self._parser.write(f)

    def get(self, section: str, key: str, fallback=None):
        """获取指定配置项"""
        return self._parser.get(section, key, fallback=fallback)

    def getint(self, section: str, key: str, fallback=0):
        """获取整数配置项"""
        return self._parser.getint(section, key, fallback=fallback)

    def getfloat(self, section: str, key: str, fallback=0.0):
        """获取浮点数配置项"""
        return self._parser.getfloat(section, key, fallback=fallback)

    def getboolean(self, section: str, key: str, fallback=False):
        """获取布尔配置项"""
        return self._parser.getboolean(section, key, fallback=fallback)

    def set(self, section: str, key: str, value):
        """设置配置项"""
        if not self._parser.has_section(section):
            self._parser.add_section(section)
        self._parser.set(section, key, str(value))

    def get_db_config(self) -> dict:
        """获取数据库配置字典"""
        return {
            "host": self.get("database", "host", "localhost"),
            "port": self.getint("database", "port", 3306),
            "username": self.get("database", "username", "root"),
            "password": self.get("database", "password", ""),
            "database": self.get("database", "database", "dangdang_data"),
        }

    def get_spider_config(self) -> dict:
        """获取爬虫配置字典"""
        return {
            "request_interval_min": self.getfloat("spider", "request_interval_min", 1.0),
            "request_interval_max": self.getfloat("spider", "request_interval_max", 3.0),
            "retry_count": self.getint("spider", "retry_count", 3),
            "timeout": self.getint("spider", "timeout", 30),
            "use_proxy": self.getboolean("spider", "use_proxy", False),
            "proxy_host": self.get("spider", "proxy_host", ""),
            "proxy_port": self.getint("spider", "proxy_port", 0),
            "proxy_type": self.get("spider", "proxy_type", "http"),
            "proxy_username": self.get("spider", "proxy_username", ""),
            "proxy_password": self.get("spider", "proxy_password", ""),
        }

    def get_server_config(self) -> dict:
        """获取Web服务器配置字典"""
        return {
            "host": self.get("server", "host", "127.0.0.1"),
            "port": self.getint("server", "port", 5000),
            "debug": self.getboolean("server", "debug", False),
        }
