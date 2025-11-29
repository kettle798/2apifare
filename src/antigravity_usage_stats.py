"""
Antigravity Usage Statistics Module
跟踪 Antigravity 模型的使用次数（claude-sonnet-4-5, gemini-3-pro）
"""

import time
from datetime import datetime, timezone, timedelta
from threading import Lock
from typing import Dict, Any, Optional

from log import log
from .storage_adapter import get_storage_adapter


def _get_next_utc_7am() -> datetime:
    """
    Calculate the next UTC 07:00 time for quota reset.
    """
    now = datetime.now(timezone.utc)
    today_7am = now.replace(hour=7, minute=0, second=0, microsecond=0)

    if now < today_7am:
        return today_7am
    else:
        return today_7am + timedelta(days=1)


class AntigravityUsageStats:
    """
    Antigravity 使用统计管理器

    每个账号跟踪：
    - claude_sonnet_4_5_calls: Claude Sonnet 4.5 系列调用次数（含 thinking）
    - gemini_3_pro_calls: Gemini 3 Pro 系列调用次数（含 high/low）
    - total_calls: 所有模型总调用次数

    限制：
    - claude_sonnet_4_5: 每天 100 次
    - gemini_3_pro: 每天 100 次
    - total: 每天 500 次
    """

    def __init__(self):
        self._lock = Lock()
        self._storage_adapter = None
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self._cache_dirty = False
        self._last_save_time = 0
        self._save_interval = 60  # 每分钟保存一次

    async def initialize(self):
        """Initialize the usage stats module."""
        if self._initialized:
            return

        self._storage_adapter = await get_storage_adapter()
        await self._load_stats()
        self._initialized = True
        log.debug("Antigravity usage statistics module initialized")

    def _is_claude_sonnet_4_5(self, model_name: str) -> bool:
        """
        检查是否是 Claude Sonnet 4.5 系列模型

        包括（共享配额）：
        - ANT/claude-sonnet-4-5
        - ANT/claude-sonnet-4-5-thinking

        注意：普通版和 thinking 版共享配额，用完任何一个整个系列都会 429
        """
        if not model_name:
            return False

        # 移除 ANT/ 前缀
        clean_model = model_name.replace("ANT/", "").lower()

        # 检查是否是 claude-sonnet-4-5 系列（含 thinking）
        return clean_model.startswith("claude-sonnet-4-5")

    def _is_gemini_3_pro(self, model_name: str) -> bool:
        """
        检查是否是 Gemini 3 Pro 系列模型

        包括（共享配额）：
        - ANT/gemini-3-pro
        - ANT/gemini-3-pro-high
        - ANT/gemini-3-pro-low
        - ANT/gemini-3-pro-image

        注意：所有 gemini-3 系列模型共享配额，用完任何一个整个系列都会 429
        """
        if not model_name:
            return False

        # 移除 ANT/ 前缀
        clean_model = model_name.replace("ANT/", "").lower()

        # 检查是否是 gemini-3 系列
        return clean_model.startswith("gemini-3")

    async def _load_stats(self):
        """Load statistics from unified storage"""
        try:
            # 从存储获取所有 Antigravity 账号的统计数据
            accounts_data = await self._storage_adapter.load_antigravity_accounts()

            if not accounts_data or "accounts" not in accounts_data:
                log.debug("No Antigravity accounts found")
                return

            # 加载每个账号的统计
            for account in accounts_data["accounts"]:
                user_id = account.get("user_id")
                if not user_id:
                    continue

                virtual_filename = f"userID_{user_id}"

                # 提取使用统计字段
                usage_data = {
                    "claude_sonnet_4_5_calls": account.get("claude_sonnet_4_5_calls", 0),
                    "gemini_3_pro_calls": account.get("gemini_3_pro_calls", 0),
                    "total_calls": account.get("total_calls", 0),
                    "next_reset_time": account.get("next_reset_time"),
                    "daily_limit_claude": account.get("daily_limit_claude", 200),
                    "daily_limit_gemini": account.get("daily_limit_gemini", 200),
                    "daily_limit_total": account.get("daily_limit_total", 1000),
                }

                self._stats_cache[virtual_filename] = usage_data

            log.debug(f"Loaded Antigravity usage statistics for {len(self._stats_cache)} accounts")

        except Exception as e:
            log.error(f"Failed to load Antigravity usage statistics: {e}")
            self._stats_cache = {}

    async def _save_stats(self):
        """Save statistics to unified storage"""
        current_time = time.time()

        # 使用脏标记和时间间隔控制
        if not self._cache_dirty or (current_time - self._last_save_time < self._save_interval):
            return

        try:
            # 读取现有的 accounts.toml
            accounts_data = await self._storage_adapter.load_antigravity_accounts()

            if not accounts_data or "accounts" not in accounts_data:
                log.error("Failed to load accounts.toml for saving stats")
                return

            # 更新每个账号的统计数据
            for virtual_filename, stats in self._stats_cache.items():
                # 提取 user_id
                user_id = virtual_filename.replace("userID_", "")

                # 查找对应的账号
                for i, account in enumerate(accounts_data["accounts"]):
                    if account.get("user_id") == user_id:
                        # 更新统计字段
                        accounts_data["accounts"][i].update({
                            "claude_sonnet_4_5_calls": stats.get("claude_sonnet_4_5_calls", 0),
                            "gemini_3_pro_calls": stats.get("gemini_3_pro_calls", 0),
                            "total_calls": stats.get("total_calls", 0),
                            "next_reset_time": stats.get("next_reset_time"),
                            "daily_limit_claude": stats.get("daily_limit_claude", 200),
                            "daily_limit_gemini": stats.get("daily_limit_gemini", 200),
                            "daily_limit_total": stats.get("daily_limit_total", 1000),
                        })
                        break

            # 保存回 accounts.toml
            await self._storage_adapter.save_antigravity_accounts(accounts_data)

            self._cache_dirty = False
            self._last_save_time = current_time
            log.debug("Successfully saved Antigravity usage statistics")

        except Exception as e:
            log.error(f"Failed to save Antigravity usage statistics: {e}")

    def _get_or_create_stats(self, virtual_filename: str) -> Dict[str, Any]:
        """Get or create statistics entry for an account"""
        if virtual_filename not in self._stats_cache:
            next_reset = _get_next_utc_7am()
            self._stats_cache[virtual_filename] = {
                "claude_sonnet_4_5_calls": 0,
                "gemini_3_pro_calls": 0,
                "total_calls": 0,
                "next_reset_time": next_reset.isoformat(),
                "daily_limit_claude": 200,
                "daily_limit_gemini": 200,
                "daily_limit_total": 1000,
            }
            self._cache_dirty = True

        return self._stats_cache[virtual_filename]

    def _check_and_reset_daily_quota(self, stats: Dict[str, Any]) -> bool:
        """
        Simple reset logic: if current time >= next_reset_time, then reset.
        """
        try:
            next_reset_str = stats.get("next_reset_time")
            if not next_reset_str:
                next_reset = _get_next_utc_7am()
                stats["next_reset_time"] = next_reset.isoformat()
                return False

            next_reset = datetime.fromisoformat(next_reset_str)
            now = datetime.now(timezone.utc)

            if now >= next_reset:
                old_claude = stats.get("claude_sonnet_4_5_calls", 0)
                old_gemini = stats.get("gemini_3_pro_calls", 0)
                old_total = stats.get("total_calls", 0)

                # Reset counters
                new_next_reset = _get_next_utc_7am()
                stats.update({
                    "claude_sonnet_4_5_calls": 0,
                    "gemini_3_pro_calls": 0,
                    "total_calls": 0,
                    "next_reset_time": new_next_reset.isoformat(),
                })

                self._cache_dirty = True
                log.info(
                    f"Antigravity daily quota reset - Claude: {old_claude}, Gemini: {old_gemini}, Total: {old_total}"
                )
                return True

            return False
        except Exception as e:
            log.error(f"Error in Antigravity daily quota reset check: {e}")
            return False

    async def record_successful_call(self, virtual_filename: str, model_name: str):
        """Record a successful API call for statistics"""
        if not self._initialized:
            await self.initialize()

        with self._lock:
            try:
                stats = self._get_or_create_stats(virtual_filename)

                # Check and perform daily reset if needed
                self._check_and_reset_daily_quota(stats)

                # Increment counters
                is_claude = self._is_claude_sonnet_4_5(model_name)
                is_gemini = self._is_gemini_3_pro(model_name)

                stats["total_calls"] += 1

                if is_claude:
                    stats["claude_sonnet_4_5_calls"] += 1
                elif is_gemini:
                    stats["gemini_3_pro_calls"] += 1

                self._cache_dirty = True

                log.debug(
                    f"Antigravity usage recorded - Account: {virtual_filename}, Model: {model_name}, "
                    f"Claude: {stats['claude_sonnet_4_5_calls']}/{stats.get('daily_limit_claude', 200)}, "
                    f"Gemini: {stats['gemini_3_pro_calls']}/{stats.get('daily_limit_gemini', 200)}, "
                    f"Total: {stats['total_calls']}/{stats.get('daily_limit_total', 1000)}"
                )

            except Exception as e:
                log.error(f"Failed to record Antigravity usage statistics: {e}")

        # Save stats asynchronously
        try:
            await self._save_stats()
        except Exception as e:
            log.error(f"Failed to save Antigravity usage statistics after recording: {e}")

    async def check_quota_available(self, virtual_filename: str, model_name: str) -> tuple[bool, str]:
        """
        检查是否还有配额可用

        Returns:
            (is_available, reason)
        """
        if not self._initialized:
            await self.initialize()

        with self._lock:
            try:
                stats = self._get_or_create_stats(virtual_filename)

                # Check daily reset
                self._check_and_reset_daily_quota(stats)

                # Check limits
                is_claude = self._is_claude_sonnet_4_5(model_name)
                is_gemini = self._is_gemini_3_pro(model_name)

                # Check total limit first
                if stats["total_calls"] >= stats.get("daily_limit_total", 1000):
                    return False, f"总调用次数已达每日限制 ({stats['total_calls']}/{stats.get('daily_limit_total', 1000)})"

                # Check model-specific limits (按系列检查，系列内所有模型共享配额)
                if is_claude:
                    if stats["claude_sonnet_4_5_calls"] >= stats.get("daily_limit_claude", 200):
                        return False, f"Claude Sonnet 4.5 系列调用次数已达每日限制 ({stats['claude_sonnet_4_5_calls']}/{stats.get('daily_limit_claude', 200)})"

                elif is_gemini:
                    if stats["gemini_3_pro_calls"] >= stats.get("daily_limit_gemini", 200):
                        return False, f"Gemini 3 Pro 系列调用次数已达每日限制 ({stats['gemini_3_pro_calls']}/{stats.get('daily_limit_gemini', 200)})"

                return True, "配额可用"

            except Exception as e:
                log.error(f"Error checking Antigravity quota: {e}")
                return True, "检查失败，允许调用"  # 检查失败时允许调用，避免阻塞

    async def get_usage_stats(self, virtual_filename: str = None) -> Dict[str, Any]:
        """Get usage statistics"""
        if not self._initialized:
            await self.initialize()

        with self._lock:
            if virtual_filename:
                stats = self._get_or_create_stats(virtual_filename)
                self._check_and_reset_daily_quota(stats)
                return {
                    "account": virtual_filename,
                    "claude_sonnet_4_5_calls": stats.get("claude_sonnet_4_5_calls", 0),
                    "gemini_3_pro_calls": stats.get("gemini_3_pro_calls", 0),
                    "total_calls": stats.get("total_calls", 0),
                    "daily_limit_claude": stats.get("daily_limit_claude", 200),
                    "daily_limit_gemini": stats.get("daily_limit_gemini", 200),
                    "daily_limit_total": stats.get("daily_limit_total", 1000),
                    "next_reset_time": stats.get("next_reset_time"),
                }
            else:
                # Return all statistics
                all_stats = {}
                for filename, stats in self._stats_cache.items():
                    self._check_and_reset_daily_quota(stats)
                    all_stats[filename] = {
                        "claude_sonnet_4_5_calls": stats.get("claude_sonnet_4_5_calls", 0),
                        "gemini_3_pro_calls": stats.get("gemini_3_pro_calls", 0),
                        "total_calls": stats.get("total_calls", 0),
                        "daily_limit_claude": stats.get("daily_limit_claude", 200),
                        "daily_limit_gemini": stats.get("daily_limit_gemini", 200),
                        "daily_limit_total": stats.get("daily_limit_total", 1000),
                        "next_reset_time": stats.get("next_reset_time"),
                    }

                return all_stats


# Global instance
_antigravity_usage_stats_instance: Optional[AntigravityUsageStats] = None


async def get_antigravity_usage_stats_instance() -> AntigravityUsageStats:
    """Get the global Antigravity usage statistics instance"""
    global _antigravity_usage_stats_instance
    if _antigravity_usage_stats_instance is None:
        _antigravity_usage_stats_instance = AntigravityUsageStats()
        await _antigravity_usage_stats_instance.initialize()
    return _antigravity_usage_stats_instance


async def record_antigravity_call(virtual_filename: str, model_name: str):
    """Convenience function to record an Antigravity API call"""
    stats = await get_antigravity_usage_stats_instance()
    await stats.record_successful_call(virtual_filename, model_name)


async def check_antigravity_quota(virtual_filename: str, model_name: str) -> tuple[bool, str]:
    """Convenience function to check Antigravity quota"""
    stats = await get_antigravity_usage_stats_instance()
    return await stats.check_quota_available(virtual_filename, model_name)
