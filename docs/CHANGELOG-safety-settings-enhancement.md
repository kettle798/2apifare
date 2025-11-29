# 安全设置增强 - 基于 gcli2api PR #118

## 改动概述

基于 [gcli2api PR #118](https://github.com/su-kaka/gcli2api/pull/118) 的思路，对本项目的安全设置处理进行了全面优化，确保所有安全分类都被正确配置，避免内容过滤导致的 API 错误。

## 主要改动

### 1. 扩展安全分类列表 (config.py)

**新增 5 个安全分类**，覆盖 Vertex AI 最新的图像和越狱检测功能：

```python
# 新增的安全分类
{"category": "HARM_CATEGORY_IMAGE_HATE", "threshold": "BLOCK_NONE"}
{"category": "HARM_CATEGORY_IMAGE_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
{"category": "HARM_CATEGORY_IMAGE_HARASSMENT", "threshold": "BLOCK_NONE"}
{"category": "HARM_CATEGORY_IMAGE_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}
{"category": "HARM_CATEGORY_JAILBREAK", "threshold": "BLOCK_NONE"}
```

**完整的安全分类列表**（共 10 个）：
- 基础分类（5 个）
  - HARM_CATEGORY_HARASSMENT
  - HARM_CATEGORY_HATE_SPEECH
  - HARM_CATEGORY_SEXUALLY_EXPLICIT
  - HARM_CATEGORY_DANGEROUS_CONTENT
  - HARM_CATEGORY_CIVIC_INTEGRITY

- 图像相关分类（4 个）
  - HARM_CATEGORY_IMAGE_HATE
  - HARM_CATEGORY_IMAGE_DANGEROUS_CONTENT
  - HARM_CATEGORY_IMAGE_HARASSMENT
  - HARM_CATEGORY_IMAGE_SEXUALLY_EXPLICIT

- 越狱检测（1 个）
  - HARM_CATEGORY_JAILBREAK

### 2. 优化安全设置合并逻辑 (src/google_chat_api.py)

**新增 `_merge_safety_settings()` 辅助函数**，实现增量补充策略：

```python
def _merge_safety_settings(user_settings: list = None) -> list:
    """
    合并用户的安全设置和默认安全设置。
    采用增量补充策略：只添加用户未配置的默认设置项，避免覆盖用户自定义设置。
    """
```

**核心优势**：
- ✅ **保护用户自定义设置**：不会覆盖用户已配置的安全分类
- ✅ **自动补充缺失项**：确保所有必需的安全分类都存在
- ✅ **向后兼容**：对于未提供安全设置的请求，使用完整默认配置

**应用范围**：
1. `build_gemini_payload_from_native()` - 原生 Gemini 请求
2. `openai_request_to_gemini_payload()` - OpenAI 转 Gemini 请求

### 3. Antigravity 路由适配 (antigravity/converter.py)

**新增功能**：为 Antigravity API 请求也添加了完整的安全设置

**实现方式**：
```python
# 在 generate_request_body() 中添加
'safetySettings': DEFAULT_SAFETY_SETTINGS  # 全部 10 个分类，全部关闭
```

**验证结果**：
- ✅ Antigravity 请求体正确包含 10 个安全设置
- ✅ 所有设置均为 BLOCK_NONE（完全开放）
- ✅ 包含所有新增的图像和越狱检测分类

## 测试验证

### 测试套件 1: GeminiCLI 安全设置合并逻辑 (`test_safety_settings_merge.py`)

包含 4 个测试场景：

1. ✅ **测试 1**：用户未提供安全设置 → 返回全部默认设置
2. ✅ **测试 2**：用户提供部分设置 → 保留用户设置 + 补充缺失项
3. ✅ **测试 3**：用户提供全部设置 → 完全保留用户配置
4. ✅ **测试 4**：验证新增分类 → 所有 5 个新分类都已添加

**测试结果**：4/4 通过 ✅

### 测试套件 2: Antigravity 安全设置验证 (`test_antigravity_safety_settings.py`)

包含 2 个测试场景：

1. ✅ **测试 1**：请求体包含完整安全设置 → 10 个分类全部 BLOCK_NONE
2. ✅ **测试 2**：请求体结构完整性 → 所有必需字段都存在

**测试结果**：2/2 通过 ✅

## 技术细节

### 合并逻辑示例

```python
# 场景 1: 用户未提供安全设置
_merge_safety_settings(None)
# → 返回全部 10 个默认设置

# 场景 2: 用户只自定义了一个分类
user_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
]
_merge_safety_settings(user_settings)
# → 返回：用户的自定义设置（1个）+ 其他默认设置（9个）= 10个

# 场景 3: 用户提供了所有分类
_merge_safety_settings(all_user_settings)
# → 返回：完全保留用户的设置，不添加任何默认项
```

### 实现原理

1. **提取用户已配置的分类**：
   ```python
   user_categories = {setting.get("category") for setting in user_settings}
   ```

2. **增量补充**：
   ```python
   for default_setting in DEFAULT_SAFETY_SETTINGS:
       if default_setting.get("category") not in user_categories:
           merged_settings.append(default_setting)
   ```

3. **避免覆盖**：用户设置始终位于列表前部，不会被默认值替换

## 影响范围

### 受益的模型（全部覆盖）

- ✅ **GeminiCLI 模型**（所有 gemini-2.5-* 模型）
  - gemini-2.5-pro-preview-06-05
  - gemini-2.5-pro
  - gemini-2.5-flash
  - 以及所有功能前缀变体（假流式/、流式抗截断/）

- ✅ **图像模型**（特别受益于新增的图像安全分类）
  - gemini-2.5-flash-image
  - gemini-2.5-flash-image-preview

- ✅ **OpenAI 兼容层**（通过 OpenAI API 调用 Gemini）

- ✅ **Antigravity 模型**（ANT/ 前缀，全部支持）
  - claude-sonnet-4-5
  - claude-sonnet-4-5-thinking
  - gemini-2.5-flash-lite
  - gemini-3-pro-high/low/image
  - gpt-oss-120b-medium
  - rev19-uic3-1p

## 向后兼容性

✅ **完全兼容**：
- 现有代码无需修改
- 现有请求行为保持不变
- 只是增强了安全设置的处理逻辑

## 与 gcli2api PR #118 的差异

| 功能 | gcli2api PR #118 | 本项目实现 |
|------|------------------|-----------|
| 新增安全分类 | ✅ 5 个 | ✅ 5 个（完全一致） |
| 合并逻辑优化 | ✅ | ✅（增强版，更完善） |
| WebSocket 优化 | ✅ | ❌（不需要，已有更好实现） |
| 调试日志增强 | ✅ | ❌（可选，未实现） |
| Antigravity 支持 | ❌（不适用） | ✅（额外实现，已测试） |
| 测试覆盖 | ❌ | ✅（6 个测试，全部通过） |

## 相关文件

### 修改的文件
- [config.py](../config.py) - 新增 5 个安全分类（共 10 个）
- [src/google_chat_api.py](../src/google_chat_api.py) - 新增合并函数 + 应用合并逻辑
- [src/openai_transfer.py](../src/openai_transfer.py) - 使用新的合并函数
- [antigravity/converter.py](../antigravity/converter.py) - 为 Antigravity 请求添加安全设置

### 新增的文件
- [test_safety_settings_merge.py](../test_safety_settings_merge.py) - GeminiCLI 合并逻辑测试
- [test_antigravity_safety_settings.py](../test_antigravity_safety_settings.py) - Antigravity 安全设置测试
- [docs/CHANGELOG-safety-settings-enhancement.md](./CHANGELOG-safety-settings-enhancement.md) - 本文档

## 运行测试

### 测试 1: GeminiCLI 安全设置合并逻辑

```bash
python test_safety_settings_merge.py
```

预期输出：
```
============================================================
安全设置合并逻辑测试
============================================================

测试 1: 用户未提供安全设置
  预期：返回全部 10 个默认设置
  实际：返回 10 个设置
  [PASS] All default categories exist

测试 2: 用户提供部分设置（自定义 HARASSMENT 阈值）
  预期：保留用户设置，补充其他 9 个默认设置
  实际：返回 10 个设置
  [PASS] User custom threshold not overwritten
  [PASS] All missing default settings were added

测试 3: 用户提供所有设置（全部自定义阈值）
  预期：保留全部用户设置，不添加额外设置
  实际：返回 10 个设置
  [PASS] All user settings preserved, not overwritten by defaults

测试 4: 验证新增的安全分类
  [PASS] All 5 new categories added
  Total default settings: 10

============================================================
测试结果：4/4 通过
============================================================
[SUCCESS] All tests passed! Safety settings merge logic works correctly.
```

### 测试 2: Antigravity 安全设置验证

```bash
python test_antigravity_safety_settings.py
```

预期输出：
```
======================================================================
Antigravity 安全设置测试
======================================================================

测试: Antigravity 请求体包含安全设置
  检查请求体是否包含 'request' 字段...
  检查是否包含 safetySettings...
  预期：10 个安全设置
  实际：10 个设置
  [PASS] All safety settings present and set to BLOCK_NONE
  [PASS] Includes all 5 new categories

测试: Antigravity 请求体结构完整性
  [PASS] All required fields present
  Top-level fields: ['project', 'requestId', 'request', 'model', 'userAgent']
  Request fields: ['contents', 'systemInstruction', 'tools', 'toolConfig',
                   'generationConfig', 'safetySettings', 'sessionId']

======================================================================
测试结果：2/2 通过
======================================================================
[SUCCESS] Antigravity 安全设置配置正确！
```

## 总结

本次改动成功地将 gcli2api PR #118 的核心优化移植到双路由项目中，并进一步扩展到 Antigravity 路由，实现了：

### 核心成果

1. ✅ **更全面的安全分类覆盖**（10 个分类，包括最新的图像和越狱检测）
   - 5 个基础分类
   - 4 个图像分类
   - 1 个越狱检测分类

2. ✅ **更智能的设置合并逻辑**（GeminiCLI 路由）
   - 保护用户自定义设置
   - 自动补充缺失分类
   - 避免意外覆盖

3. ✅ **完整的双路由支持**
   - **GeminiCLI**：智能合并逻辑 + 完整安全设置
   - **Antigravity**：直接注入完整安全设置

4. ✅ **全面的测试验证**
   - GeminiCLI 测试：4/4 通过 ✅
   - Antigravity 测试：2/2 通过 ✅
   - 总计：6/6 测试全部通过 🎉

### 用户体验

对于您的用户群体（酒馆/AI 女友玩家）：

- 🎯 **默认完全开放**：所有 10 个安全分类都是 BLOCK_NONE
- 🎯 **无需任何配置**：开箱即用，无内容限制
- 🎯 **支持所有模型**：GeminiCLI + Antigravity 全覆盖
- 🎯 **不会意外被过滤**：包含所有最新的安全分类

### 技术价值

这些改进将有效：
- 减少因缺少安全分类导致的 API 错误
- 避免内容被意外过滤
- 提升系统稳定性和用户体验
- 为未来 Google 新增的安全分类做好准备
