"""
Antigravity API 客户端
基于 antigravity2api-nodejs/src/api/client.js
"""
import json
import httpx
from typing import Dict, Any, Optional, AsyncGenerator, Callable
from urllib.parse import urlparse
import logging

log = logging.getLogger("antigravity.client")

# User Agent 配置
USER_AGENT = "antigravity/1.11.3 windows/amd64"


def extract_host_from_url(url: str) -> str:
    """从 URL 中提取 Host"""
    parsed = urlparse(url)
    return parsed.netloc


async def stream_generate_content(
    request_body: Dict[str, Any],
    access_token: str,
    proxy: Optional[str] = None,
    timeout: int = 120
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    调用 Google Antigravity API 生成内容（流式）

    Args:
        request_body: 请求体（由 converter.generate_request_body 生成）
        access_token: OAuth access token
        proxy: 代理地址
        timeout: 超时时间（秒）

    Yields:
        {'type': 'text'|'thinking'|'tool_calls', 'content': str, 'tool_calls': [...]}

    Raises:
        httpx.HTTPError: 请求失败
        ValueError: 响应解析失败
    """
    # 动态获取 API 端点配置
    from config import get_antigravity_api_endpoint

    api_url = await get_antigravity_api_endpoint()
    api_host = extract_host_from_url(api_url)

    headers = {
        'Host': api_host,
        'User-Agent': USER_AGENT,
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip'
    }

    thinking_started = False
    tool_calls = []

    try:
        # 配置代理（httpx 使用 proxy 参数，不是 proxies）
        client_kwargs = {'timeout': timeout}
        if proxy:
            client_kwargs['proxy'] = proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            async with client.stream('POST', api_url, json=request_body, headers=headers) as response:
                # 检查响应状态
                if response.status_code == 403:
                    error_text = await response.aread()
                    raise ValueError(f"403 Forbidden - 该账号没有使用权限: {error_text.decode('utf-8', errors='ignore')}")

                if response.status_code != 200:
                    error_text = await response.aread()
                    raise httpx.HTTPError(f"API 请求失败 ({response.status_code}): {error_text.decode('utf-8', errors='ignore')}")

                # 处理 SSE 流
                async for line in response.aiter_lines():
                    # 跳过空行和非 data: 开头的行
                    if not line or not line.startswith('data: '):
                        continue

                    # 提取 JSON 数据
                    json_str = line[6:]  # 去掉 'data: '

                    # 跳过 [DONE] 标记
                    if json_str.strip() == '[DONE]':
                        break

                    try:
                        data = json.loads(json_str)

                        # 提取 candidates[0].content.parts
                        candidates = data.get('response', {}).get('candidates', [])
                        if not candidates:
                            continue

                        candidate = candidates[0]
                        parts = candidate.get('content', {}).get('parts', [])

                        for part in parts:
                            # Thinking 模式
                            if part.get('thought') is True:
                                if not thinking_started:
                                    yield {'type': 'thinking', 'content': '<think>\n'}
                                    thinking_started = True
                                yield {'type': 'thinking', 'content': part.get('text', '')}

                            # 普通文本
                            elif 'text' in part:
                                if thinking_started:
                                    yield {'type': 'thinking', 'content': '\n</think>\n'}
                                    thinking_started = False
                                yield {'type': 'text', 'content': part.get('text', '')}

                            # 函数调用
                            elif 'functionCall' in part:
                                function_call = part['functionCall']
                                tool_calls.append({
                                    'id': function_call.get('id', ''),
                                    'type': 'function',
                                    'function': {
                                        'name': function_call.get('name', ''),
                                        'arguments': function_call.get('args', {}).get('query', '{}')
                                    }
                                })

                        # 当遇到 finishReason 时，发送所有收集的工具调用
                        finish_reason = candidate.get('finishReason')
                        if finish_reason and tool_calls:
                            if thinking_started:
                                yield {'type': 'thinking', 'content': '\n</think>\n'}
                                thinking_started = False
                            yield {'type': 'tool_calls', 'tool_calls': tool_calls}
                            tool_calls = []

                    except json.JSONDecodeError:
                        # 忽略 JSON 解析错误（可能是不完整的数据）
                        continue
                    except Exception as e:
                        log.warning(f"处理 SSE 数据时出错: {e}")
                        continue

    except httpx.TimeoutException:
        raise httpx.HTTPError(f"请求超时（超过 {timeout} 秒）")
    except Exception as e:
        log.error(f"API 请求失败: {e}")
        raise


async def get_available_models(
    access_token: str,
    proxy: Optional[str] = None,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    获取可用模型列表

    Args:
        access_token: OAuth access token
        proxy: 代理地址
        timeout: 超时时间（秒）

    Returns:
        {'object': 'list', 'data': [{'id': str, 'object': 'model', ...}]}

    Raises:
        httpx.HTTPError: 请求失败
    """
    # 动态获取模型列表端点配置
    from config import get_antigravity_models_endpoint

    models_url = await get_antigravity_models_endpoint()
    api_host = extract_host_from_url(models_url)

    headers = {
        'Host': api_host,
        'User-Agent': USER_AGENT,
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip'
    }

    try:
        # 配置代理（httpx 使用 proxy 参数，不是 proxies）
        client_kwargs = {'timeout': timeout}
        if proxy:
            client_kwargs['proxy'] = proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.post(models_url, json={}, headers=headers)

            if response.status_code != 200:
                error_text = response.text
                raise httpx.HTTPError(f"获取模型列表失败 ({response.status_code}): {error_text}")

            data = response.json()

            # 转换为 OpenAI 格式
            models = data.get('models', {})
            return {
                'object': 'list',
                'data': [
                    {
                        'id': model_id,
                        'object': 'model',
                        'created': 1700000000,  # 固定时间戳
                        'owned_by': 'google'
                    }
                    for model_id in models.keys()
                ]
            }

    except httpx.TimeoutException:
        raise httpx.HTTPError(f"获取模型列表超时（超过 {timeout} 秒）")
    except Exception as e:
        log.error(f"获取模型列表失败: {e}")
        raise


def convert_sse_to_openai_format(
    sse_chunk: Dict[str, Any],
    model: str,
    stream_id: Optional[str] = None,
    created: Optional[int] = None
) -> str:
    """
    将 Antigravity SSE 块转换为 OpenAI 流式格式

    Args:
        sse_chunk: {'type': 'text'|'thinking'|'tool_calls', 'content': str, 'tool_calls': [...]}
        model: 模型名称
        stream_id: 流 ID
        created: 创建时间戳

    Returns:
        OpenAI 格式的 SSE 数据行（data: {...}\n\n）
    """
    import time

    if not stream_id:
        stream_id = f"chatcmpl-{int(time.time() * 1000)}"
    if not created:
        created = int(time.time())

    # [FIX] 完全过滤掉 thinking 类型的 chunk（包括 <think> 标签）
    chunk_type = sse_chunk.get('type')

    if chunk_type == 'thinking':
        # thinking 内容不输出到前端，返回空字符串
        return ""

    if chunk_type == 'tool_calls':
        # 工具调用
        chunk = {
            'id': stream_id,
            'object': 'chat.completion.chunk',
            'created': created,
            'model': model,
            'choices': [{
                'index': 0,
                'delta': {
                    'tool_calls': sse_chunk['tool_calls']
                },
                'finish_reason': None
            }]
        }
    elif chunk_type == 'text':
        # 只输出实际的文本内容（不包括 thinking）
        chunk = {
            'id': stream_id,
            'object': 'chat.completion.chunk',
            'created': created,
            'model': model,
            'choices': [{
                'index': 0,
                'delta': {
                    'content': sse_chunk.get('content', '')
                },
                'finish_reason': None
            }]
        }
    else:
        # 未知类型，不输出
        return ""

    return f"data: {json.dumps(chunk)}\n\n"


def generate_finish_chunk(
    model: str,
    has_tool_calls: bool,
    stream_id: Optional[str] = None,
    created: Optional[int] = None
) -> str:
    """
    生成结束块

    Args:
        model: 模型名称
        has_tool_calls: 是否有工具调用
        stream_id: 流 ID
        created: 创建时间戳

    Returns:
        OpenAI 格式的结束块（data: {...}\n\ndata: [DONE]\n\n）
    """
    import time

    if not stream_id:
        stream_id = f"chatcmpl-{int(time.time() * 1000)}"
    if not created:
        created = int(time.time())

    finish_reason = 'tool_calls' if has_tool_calls else 'stop'

    chunk = {
        'id': stream_id,
        'object': 'chat.completion.chunk',
        'created': created,
        'model': model,
        'choices': [{
            'index': 0,
            'delta': {},
            'finish_reason': finish_reason
        }]
    }

    return f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"
