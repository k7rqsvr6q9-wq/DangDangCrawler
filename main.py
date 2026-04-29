"""应用程序入口文件：启动Flask Web服务器并自动打开浏览器"""

import sys
import webbrowser
import threading

from dangdang_crawler.utils.config import ConfigManager
from dangdang_crawler.utils.logger import LoggerManager
from dangdang_crawler.web.app import create_app


def main():
    """应用程序主函数"""
    # 初始化日志系统
    logger_mgr = LoggerManager()
    logger = logger_mgr.get_logger("main")
    logger.info("系统启动")

    # 加载配置
    config = ConfigManager()
    server_cfg = config.get_server_config()

    # 创建Flask应用
    app = create_app(config)

    host = server_cfg.get("host", "127.0.0.1")
    port = server_cfg.get("port", 5000)
    url = f"http://{host}:{port}"

    # 延迟1秒后自动打开浏览器
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(url)
        logger.info(f"已在浏览器中打开: {url}")

    threading.Thread(target=open_browser, daemon=True).start()

    # 启动Flask服务器
    logger.info(f"Web服务器启动: {url}")
    print(f"\n当当网图书榜单爬虫系统")
    print(f"浏览器访问: {url}")
    print(f"按 Ctrl+C 停止服务器\n")

    app.run(host=host, port=port, debug=server_cfg.get("debug", False))


if __name__ == "__main__":
    main()
