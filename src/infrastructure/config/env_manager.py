"""
配置读写入口（兼容层）。

真正的存储是 data/config.jsonc，由 config_store 负责读写与加密。
env_file 只作为首次迁移的来源，不再写入。
配置优先级：data/config.jsonc > 进程环境变量 > 代码默认值。
"""
from typing import Dict, List, Optional
from pathlib import Path

from dotenv import dotenv_values


class EnvManager:
    """把旧的 env 接口转发到 config_store。

    写操作只进 config_store；读操作先看 config_store，
    再回退到 env_file（迁移期保留 data/.env 里的历史值）。
    """

    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)

    def _file_values(self) -> Dict[str, str]:
        if not self.env_file.exists():
            return {}
        loaded = dotenv_values(self.env_file, encoding="utf-8")
        return {key: value for key, value in loaded.items() if key and value is not None}

    def read_env(self) -> Dict[str, str]:
        from src.infrastructure.config.store import config_store

        merged = {key: str(value) for key, value in config_store.plain_mapping().items()}
        for key, value in self._file_values().items():
            merged.setdefault(key, value)
        return merged

    def get_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        from src.infrastructure.config.store import config_store

        value = config_store.get(key)
        if value is not None:
            return value
        file_value = self._file_values().get(key)
        if file_value is not None:
            return file_value
        return default

    def update_values(self, updates: Dict[str, str]) -> bool:
        return self.apply_changes(updates=updates)

    def apply_changes(
        self,
        updates: Dict[str, str],
        deletions: List[str] | None = None,
    ) -> bool:
        try:
            from src.infrastructure.config.store import config_store

            payload: Dict[str, str] = {key: value for key, value in updates.items()}
            for key in deletions or []:
                payload[key] = ""
            config_store.apply(payload)
            return True
        except Exception as e:
            print(f"更新配置失败: {e}")
            return False

    def set_value(self, key: str, value: str) -> bool:
        return self.update_values({key: value})

    def delete_keys(self, keys: List[str]) -> bool:
        return self.apply_changes(updates={}, deletions=keys)


# 首次启动时从这里读取旧配置，生成 data/config.jsonc
env_manager = EnvManager("data/.env")
