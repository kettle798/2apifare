#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存诊断工具 - 分析各组件内存占用
用于 898MB RAM 服务器的内存优化分析
"""

import sys
import asyncio
import tracemalloc
from collections import deque
from typing import Dict, Any
import psutil
import os


def format_size(bytes_size: int) -> str:
    """格式化字节大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def get_deep_size(obj, seen=None) -> int:
    """递归计算对象的真实内存占用（包括引用对象）"""
    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0

    seen.add(obj_id)

    if isinstance(obj, dict):
        size += sum([get_deep_size(v, seen) for v in obj.values()])
        size += sum([get_deep_size(k, seen) for k in obj.keys()])
    elif hasattr(obj, '__dict__'):
        size += get_deep_size(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        try:
            size += sum([get_deep_size(i, seen) for i in obj])
        except:
            pass

    return size


class MemoryDiagnostic:
    """内存诊断器"""

    def __init__(self):
        self.results = {}
        self.process = psutil.Process(os.getpid())

    def get_system_memory(self) -> Dict[str, Any]:
        """获取系统内存信息"""
        mem = psutil.virtual_memory()
        process_mem = self.process.memory_info()

        return {
            "系统总内存": format_size(mem.total),
            "系统已用内存": format_size(mem.used),
            "系统可用内存": format_size(mem.available),
            "系统内存使用率": f"{mem.percent}%",
            "进程占用内存 (RSS)": format_size(process_mem.rss),
            "进程虚拟内存 (VMS)": format_size(process_mem.vms),
        }

    async def analyze_usage_stats(self):
        """分析 usage_stats.py 内存占用"""
        try:
            from src.usage_stats import UsageStats
            from src.storage_adapter import get_storage_adapter

            # 创建实例
            storage = await get_storage_adapter()
            stats = UsageStats(storage)
            await stats.initialize()

            # 计算内存
            total_size = get_deep_size(stats)
            cache_size = get_deep_size(stats._stats_cache)
            deque_size = get_deep_size(stats._operation_times)

            # 估算不同 max_cache_size 的内存占用
            current_max = stats._max_cache_size
            single_entry_size = cache_size / max(len(stats._stats_cache), 1)

            self.results["UsageStats"] = {
                "总内存占用": format_size(total_size),
                "缓存占用": format_size(cache_size),
                "缓存条目数": len(stats._stats_cache),
                "当前 max_cache_size": current_max,
                "单条缓存平均大小": format_size(single_entry_size),
                "性能监控 deque 占用": format_size(deque_size),
                "deque maxlen": stats._operation_times.maxlen,
                "保存间隔": f"{stats._save_interval}秒",
                "优化方案": {
                    "方案1: max_cache_size 100→30": {
                        "节省内存": format_size(single_entry_size * 70),
                        "代价": "只保留最近30个凭证的统计，旧凭证统计会被淘汰"
                    },
                    "方案2: deque maxlen 1000→100": {
                        "节省内存": format_size(deque_size * 0.9),
                        "代价": "性能监控精度降低，但影响很小"
                    },
                    "方案3: save_interval 60→120秒": {
                        "节省内存": "0 (不节省内存，但减少磁盘IO)",
                        "代价": "数据丢失风险增加60秒窗口"
                    }
                }
            }

        except Exception as e:
            self.results["UsageStats"] = {"错误": str(e)}

    async def analyze_antigravity_usage_stats(self):
        """分析 antigravity_usage_stats.py 内存占用"""
        try:
            from src.antigravity_usage_stats import AntigravityUsageStats
            from src.storage_adapter import get_storage_adapter

            storage = await get_storage_adapter()
            stats = AntigravityUsageStats(storage)
            await stats.initialize()

            total_size = get_deep_size(stats)
            cache_size = get_deep_size(stats._stats_cache)

            self.results["AntigravityUsageStats"] = {
                "总内存占用": format_size(total_size),
                "缓存占用": format_size(cache_size),
                "缓存账号数": len(stats._stats_cache),
                "保存间隔": f"{stats._save_interval}秒",
            }

        except Exception as e:
            self.results["AntigravityUsageStats"] = {"错误": str(e)}

    async def analyze_cache_manager(self):
        """分析 cache_manager.py 内存占用"""
        try:
            from src.storage.cache_manager import UnifiedCacheManager

            # 估算单个实例的内存占用
            test_cache = {}
            for i in range(100):
                test_cache[f"key_{i}"] = {"data": "x" * 1000}

            cache_100_size = get_deep_size(test_cache)
            single_entry_size = cache_100_size / 100

            # 估算 deque 内存
            test_deque = deque(maxlen=1000)
            for i in range(1000):
                test_deque.append(0.123456)  # 模拟 operation_time
            deque_1000_size = get_deep_size(test_deque)

            self.results["UnifiedCacheManager"] = {
                "说明": "每个存储后端可能创建1个实例",
                "100条缓存估算": format_size(cache_100_size),
                "单条缓存估算": format_size(single_entry_size),
                "deque(maxlen=1000) 估算": format_size(deque_1000_size),
                "优化方案": {
                    "deque maxlen 1000→100": {
                        "节省内存": format_size(deque_1000_size * 0.9),
                        "代价": "性能监控历史减少，影响很小"
                    }
                }
            }

        except Exception as e:
            self.results["UnifiedCacheManager"] = {"错误": str(e)}

    async def analyze_ip_manager(self):
        """分析 ip_manager.py 内存占用"""
        try:
            from src.ip_manager import IPManager

            ip_mgr = IPManager()
            await ip_mgr.load()

            total_size = get_deep_size(ip_mgr)
            ip_records_size = get_deep_size(ip_mgr.ip_records)

            self.results["IPManager"] = {
                "总内存占用": format_size(total_size),
                "IP记录占用": format_size(ip_records_size),
                "IP记录数量": len(ip_mgr.ip_records),
                "单条IP记录估算": format_size(ip_records_size / max(len(ip_mgr.ip_records), 1)),
            }

        except Exception as e:
            self.results["IPManager"] = {"错误": str(e)}

    async def analyze_credential_managers(self):
        """分析凭证管理器内存占用"""
        try:
            # GeminiCLI 凭证管理器
            from src.credential_manager import get_credential_manager
            cred_mgr = await get_credential_manager()

            cred_mgr_size = get_deep_size(cred_mgr)

            self.results["CredentialManager (GeminiCLI)"] = {
                "总内存占用": format_size(cred_mgr_size),
                "凭证文件数量": len(cred_mgr._credential_files),
            }

        except Exception as e:
            self.results["CredentialManager (GeminiCLI)"] = {"错误": str(e)}

        try:
            # Antigravity 凭证管理器
            from src.antigravity_credential_manager import get_antigravity_credential_manager
            ant_mgr = await get_antigravity_credential_manager()

            ant_mgr_size = get_deep_size(ant_mgr)

            self.results["AntigravityCredentialManager"] = {
                "总内存占用": format_size(ant_mgr_size),
                "账号数量": len(ant_mgr._credential_accounts),
            }

        except Exception as e:
            self.results["AntigravityCredentialManager"] = {"错误": str(e)}

    def analyze_module_imports(self):
        """分析已导入模块的内存占用"""
        import_sizes = {}

        for name, module in sys.modules.items():
            if name.startswith('src.') or name == 'fastapi' or name == 'httpx':
                try:
                    size = get_deep_size(module)
                    import_sizes[name] = size
                except:
                    pass

        # 排序
        sorted_imports = sorted(import_sizes.items(), key=lambda x: x[1], reverse=True)[:10]

        self.results["已导入模块 (Top 10)"] = {
            name: format_size(size) for name, size in sorted_imports
        }

    def print_report(self):
        """打印诊断报告"""
        print("\n" + "="*80)
        print("内存诊断报告 - 2apifare 服务器")
        print("="*80)

        # 系统内存
        sys_mem = self.get_system_memory()
        print("\n【系统内存状态】")
        for key, value in sys_mem.items():
            print(f"  {key}: {value}")

        # 各组件详情
        for component, data in self.results.items():
            print(f"\n【{component}】")
            self._print_dict(data, indent=2)

        # 总结和建议
        self._print_recommendations()

    def _print_dict(self, d: dict, indent: int = 0):
        """递归打印字典"""
        for key, value in d.items():
            if isinstance(value, dict):
                print(" " * indent + f"{key}:")
                self._print_dict(value, indent + 2)
            else:
                print(" " * indent + f"{key}: {value}")

    def _print_recommendations(self):
        """打印优化建议"""
        print("\n" + "="*80)
        print("优化建议汇总")
        print("="*80)

        print("\n【高优先级 - 立即可执行】")
        print("  1. UsageStats deque maxlen: 1000 → 100")
        print("     - 预计节省: ~20-50KB 每实例")
        print("     - 代价: 性能监控历史减少，影响极小")
        print("     - 文件: src/usage_stats.py:79")

        print("\n  2. UnifiedCacheManager deque maxlen: 1000 → 100")
        print("     - 预计节省: ~20-50KB 每实例")
        print("     - 代价: 性能监控历史减少，影响极小")
        print("     - 文件: src/storage/cache_manager.py:79")

        print("\n【中优先级 - 需评估后执行】")
        print("  3. UsageStats max_cache_size: 100 → 30")
        print("     - 预计节省: 视单条缓存大小，可能 100KB-1MB")
        print("     - 代价: 只保留最近30个凭证的统计")
        print("     - 建议: 先看诊断结果中的'缓存条目数'，如果接近100再优化")

        print("\n【低优先级 - 优化收益较小】")
        print("  4. save_interval: 60秒 → 120秒")
        print("     - 预计节省: 0 (不节省内存)")
        print("     - 收益: 减少磁盘IO频率")
        print("     - 代价: 异常退出时数据丢失窗口增加60秒")

        print("\n【需要进一步分析】")
        print("  5. 如果 IP记录数量 > 1000，考虑添加自动清理旧记录机制")
        print("  6. 如果 凭证文件数量 很多，考虑按需加载而非全部加载到内存")

        print("\n" + "="*80)


async def main():
    """主函数"""
    print("启动内存诊断...")
    print("服务器限制: 898MB RAM")
    print("目标: 识别内存消耗源，提供优化建议\n")

    # 启动内存追踪
    tracemalloc.start()

    diagnostic = MemoryDiagnostic()

    # 执行各项分析
    print("正在分析各组件...")
    await diagnostic.analyze_usage_stats()
    print("  [OK] UsageStats 分析完成")

    await diagnostic.analyze_antigravity_usage_stats()
    print("  [OK] AntigravityUsageStats 分析完成")

    await diagnostic.analyze_cache_manager()
    print("  [OK] UnifiedCacheManager 分析完成")

    await diagnostic.analyze_ip_manager()
    print("  [OK] IPManager 分析完成")

    await diagnostic.analyze_credential_managers()
    print("  [OK] CredentialManagers 分析完成")

    diagnostic.analyze_module_imports()
    print("  [OK] 模块导入分析完成")

    # 打印报告
    diagnostic.print_report()

    # 内存追踪快照
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')

    print("\n【内存分配热点 Top 10】")
    for stat in top_stats[:10]:
        print(f"  {stat}")

    tracemalloc.stop()


if __name__ == "__main__":
    asyncio.run(main())
