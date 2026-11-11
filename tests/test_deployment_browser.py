"""Opt-in real Chromium acceptance: RUN_WEB_BROWSER_TESTS=1 uv run --extra Schedule pytest ..."""

import os
import re
import socket
import threading
import time

import pytest
import uvicorn

from src.deployment.app import create_app
from src.deployment.auth import create_credentials
from src.deployment.config import ComposeDocument
from src.deployment.setup import initialize_source
from tests.test_deployment_api import FakeRunner
from tests.test_deployment_config import SOURCE

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_WEB_BROWSER_TESTS") != "1",
    reason="Set RUN_WEB_BROWSER_TESTS=1 to run real Chromium acceptance",
)


def test_source_browser_form_text_conflict_restore_and_groups(tmp_path):
    import shutil
    from pathlib import Path

    from playwright.sync_api import expect, sync_playwright

    from src.deployment.runtime import build_app

    (tmp_path / "configs").mkdir()
    for template in Path("configs").glob("*.toml.template"):
        shutil.copyfile(template, tmp_path / "configs" / template.name)
    store = initialize_source(tmp_path, "test-password")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(build_app(tmp_path), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() > deadline:
                raise AssertionError("Source panel did not start")
            time.sleep(0.02)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{port}")
            page.locator("#password").fill("test-password")
            page.get_by_role("button", name="登录", exact=True).click()
            expect(page.locator("#config-area")).to_be_visible()
            expect(page.locator("#compose-page")).to_be_hidden()
            expect(page.get_by_label("数据库密码", exact=True)).to_have_attribute(
                "type", "password"
            )
            page.get_by_label("Bot 名称", exact=True).fill("源码测试")
            page.locator("#config-text-tab").click()
            expect(page.locator("#config-source")).to_have_value(re.compile("源码测试"))
            source = page.locator("#config-source").input_value()
            page.locator("#config-source").fill("[broken")
            page.locator("#config-form-tab").click()
            expect(page.locator("#notice")).to_contain_text("TOML 格式错误")
            expect(page.locator("#config-source")).to_have_value("[broken")
            page.locator("#config-source").fill(source)
            page.locator("#config-save").click()
            expect(page.locator("#notice")).to_contain_text("重启 Bot")
            assert "源码测试" in store.read("bot.toml")["source"]
            page.get_by_role("button", name="预览恢复配置", exact=True).first.click()
            page.locator("#confirm-action").click()
            expect(page.get_by_label("Bot 名称", exact=True)).to_have_value("Theresa")
            page.locator("#config-file").select_option("groups.toml")
            page.locator("#config-new-group").fill("12345")
            page.locator("#config-new-plugin").fill("ExamplePlugin")
            page.get_by_role("button", name="添加群 / 插件", exact=True).click()
            expect(page.get_by_text("群 12345", exact=True)).to_be_visible()
            page.locator("#config-text-tab").click()
            expect(page.locator("#config-source")).to_have_value(re.compile("ExamplePlugin = true"))
            page.locator("#config-file").select_option("ai.toml")
            expect(page.locator("#confirm-dialog")).to_be_visible()
            page.locator("#confirm-cancel").click()
            expect(page.locator("#config-file")).to_have_value("groups.toml")
            for width in (320, 768, 1024, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert errors == []
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_browser_edit_validate_save_restore_and_mobile(tmp_path):
    from playwright.sync_api import expect, sync_playwright

    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    document = ComposeDocument(tmp_path, tmp_path / ".webcontroller")
    app = create_app(document, FakeRunner(), create_credentials("test-password"))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() > deadline:
                raise AssertionError("Preview server did not start")
            time.sleep(0.02)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{port}")
            page.locator("#password").fill("test-password")
            page.get_by_role("button", name="登录", exact=True).click()
            expect(page.locator("#workspace")).to_be_visible()
            expect(page.locator("#field-image")).to_have_value("panel:1")
            page.locator("#field-image").fill("postgres:19")
            page.get_by_role("button", name="完整 YAML", exact=True).click()
            expect(page.locator("#source")).to_have_value(re.compile("postgres:19"))
            original = page.locator("#source").input_value()
            page.locator("#source").fill("services: [")
            page.get_by_role("button", name="服务配置", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("YAML 格式错误")
            expect(page.locator("#source")).to_have_value("services: [")
            page.locator("#source").fill(original)
            page.get_by_role("button", name="校验并保存", exact=True).click()
            expect(page.locator("#save-state")).to_have_text("已保存")
            assert "postgres:19" in document.source()
            page.reload()
            expect(page.locator("#save-state")).to_have_text("已保存")
            page.get_by_role("button", name="预览恢复", exact=True).first.click()
            expect(page.locator("#confirm-diff")).to_contain_text("postgres:18")
            page.locator("#confirm-action").click()
            expect(page.locator("#notice")).to_have_text("备份已恢复。")
            expect(page.locator("#save-state")).to_have_text("已保存")
            assert document.source() == SOURCE
            page.get_by_role("button", name="服务配置", exact=True).click()
            page.locator("#service-list").get_by_role(
                "button", name="webcontroller", exact=True
            ).click()
            expect(page.locator("#field-image")).to_have_value("panel:1")
            for width in (320, 768, 1024, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(tmp_path / "panel-desktop.png"), full_page=True)
            page.locator("#configs-page").click()
            expect(page.locator("#config-area")).to_be_visible()
            page.locator("#config-file").select_option("plugins.toml")
            page.locator("#config-text-tab").click()
            page.locator("#config-source").fill("[Example]\nenable = true\n")
            page.locator("#config-save").click()
            expect(page.locator("#notice")).to_contain_text("重启 Bot")
            assert (tmp_path / "configs/plugins.toml").is_file()
            page.locator("#compose-page").click()
            expect(page.locator("#compose-area")).to_be_visible()
            assert errors == []
            page.get_by_role("button", name="退出登录", exact=True).click()
            expect(page.locator("#login-panel")).to_be_visible()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
