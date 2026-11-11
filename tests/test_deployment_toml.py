from pathlib import Path

import pytest

from src.deployment.config import DeploymentError
from src.deployment.toml_config import ConfigStore


@pytest.fixture
def store(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "plugins.toml").write_text(
        '# 注释\n[Example]\nenable = false\ncustom = "保留"\n', encoding="utf-8"
    )
    return ConfigStore(tmp_path, tmp_path / ".webcontroller")


def test_patch_save_restore_and_conflict(store):
    original = store.read("plugins.toml")
    patched = store.patch(
        "plugins.toml", original["source"], [{"path": ["Example", "enable"], "value": True}]
    )
    assert "# 注释" in patched and 'custom = "保留"' in patched
    saved = store.save("plugins.toml", patched, original["version"])
    assert saved["version"] != original["version"]
    with pytest.raises(DeploymentError, match="其他操作"):
        store.save("plugins.toml", patched, original["version"])
    backup = store.backups("plugins.toml")[0]["id"]
    store.save("plugins.toml", store.backup_source("plugins.toml", backup), saved["version"])
    assert store.read("plugins.toml")["source"] == original["source"]
    assert store.backups("groups.toml") == []


def test_invalid_and_missing_files_can_be_repaired(store):
    path = store.root / "configs" / "groups.toml"
    missing = store.read("groups.toml")
    assert not missing["exists"]
    saved = store.save("groups.toml", '["123"]\nExample = true\n', missing["version"])
    path.write_text("[broken", encoding="utf-8")
    broken = store.read("groups.toml")
    assert broken["error"] and broken["source"] == "[broken"
    store.save("groups.toml", saved["source"], broken["version"])
    assert store.backup_source("groups.toml", store.backups("groups.toml")[0]["id"]) == "[broken"


@pytest.mark.parametrize("name", ["../bot.toml", "anything.toml", "credentials.json"])
def test_file_allowlist(store, name):
    with pytest.raises(DeploymentError):
        store.read(name)


def test_symlink_directory_escape(store, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = store.root / "configs" / "ai.toml"
    try:
        target.symlink_to(outside / "secret")
    except OSError:
        pytest.skip("Symlink creation unavailable")
    with pytest.raises(DeploymentError):
        store.read("ai.toml")


@pytest.mark.parametrize(
    "name,source",
    [
        ("groups.toml", "[abc]\nX = true"),
        ("plugins.toml", '[X]\nenable = "yes"'),
        ("scheduler.toml", "[X]\nkwargs = 3"),
        ("bot.toml", "[Init]\ndebug = true"),
    ],
)
def test_validation(store, name, source):
    with pytest.raises(DeploymentError):
        store.validate(name, source)


def test_templates_are_valid(store):
    for path in Path("configs").glob("*.toml.template"):
        store.validate(path.name.removesuffix(".template"), path.read_text(encoding="utf-8"))


def test_unknown_toml_types_survive_form_patch(store):
    source = "[Example]\nenable = false\ncustom = nan\ndate = 2026-10-06\n"
    data = store.read("plugins.toml")
    store.save("plugins.toml", source, data["version"])
    assert store.read("plugins.toml")["values"]["Example"]["custom"] == "nan"
    patched = store.patch("plugins.toml", source, [{"path": ["Example", "enable"], "value": True}])
    assert "custom = nan" in patched and "date = 2026-10-06" in patched
    with pytest.raises(DeploymentError, match="空值"):
        store.patch("plugins.toml", source, [{"path": ["Example", "enable"], "value": None}])


def test_failed_atomic_replace_keeps_original(store, monkeypatch):
    original = store.read("plugins.toml")

    def fail_replace(*args):
        raise PermissionError("secret path must not be exposed")

    monkeypatch.setattr("src.config_schema.os.replace", fail_replace)
    with pytest.raises(DeploymentError, match="写入配置失败") as error:
        store.save("plugins.toml", original["source"].replace("false", "true"), original["version"])
    assert "secret" not in str(error.value)
    assert store.read("plugins.toml")["source"] == original["source"]
    assert not list(store.root.rglob(".tmp-*"))


def test_directory_junction_escape(store, tmp_path):
    import os
    import subprocess

    if os.name != "nt":
        pytest.skip("Windows junction test")
    outside = tmp_path / "outside"
    outside.mkdir()
    configs = store.root / "configs"
    configs.rename(store.root / "original-configs")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(configs), str(outside)], capture_output=True
    )
    if result.returncode:
        pytest.skip("Junction creation unavailable")
    try:
        with pytest.raises(DeploymentError):
            store.read("plugins.toml")
    finally:
        # Remove only the junction itself, never recursively traverse its target.
        configs.rmdir()
