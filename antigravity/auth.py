import os
import time
import toml
import httpx
import logging
from typing import Dict, Any, Optional

# 配置日志
log = logging.getLogger("antigravity.auth")

# 常量定义 (来自 antigravity2api-nodejs)
CLIENT_ID = '1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com'
CLIENT_SECRET = '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'
SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/cclog',
    'https://www.googleapis.com/auth/experimentsandconfigs'
]

# 凭证文件路径
CREDS_FILE = os.path.join(os.getcwd(), 'creds', 'accounts.toml')

def generate_auth_url(redirect_uri: str, state: str = 'antigravity_auth') -> str:
    """生成 OAuth 认证链接"""
    params = {
        'access_type': 'offline',
        'client_id': CLIENT_ID,
        'prompt': 'consent',
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'state': state
    }
    
    # 构建查询字符串
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"

async def exchange_code_for_token(code: str, redirect_uri: str) -> Dict[str, Any]:
    """使用授权码交换 Token"""
    token_url = "https://oauth2.googleapis.com/token"

    data = {
        'code': code,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            log.error(f"Token exchange failed: {e.response.text}")
            raise Exception(f"Token exchange failed: {e.response.text}")
        except Exception as e:
            log.error(f"Token exchange error: {e}")
            raise

async def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """使用 access_token 获取用户信息"""
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(userinfo_url, headers=headers)
            response.raise_for_status()
            user_info = response.json()
            log.info(f"成功获取用户信息: {user_info.get('email', 'unknown')}")
            return user_info
        except httpx.HTTPStatusError as e:
            log.error(f"获取用户信息失败: {e.response.text}")
            return None
        except Exception as e:
            log.error(f"获取用户信息出错: {e}")
            return None

async def get_project_info(access_token: str) -> Optional[Dict[str, Any]]:
    """获取用户的 Google Cloud 项目信息"""
    projects_url = "https://cloudresourcemanager.googleapis.com/v1/projects"

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(projects_url, headers=headers)
            response.raise_for_status()
            projects_data = response.json()
            projects = projects_data.get('projects', [])
            log.info(f"成功获取 {len(projects)} 个项目信息")
            return projects
        except httpx.HTTPStatusError as e:
            log.warning(f"获取项目信息失败: {e.response.text}")
            return None
        except Exception as e:
            log.warning(f"获取项目信息出错: {e}")
            return None

async def save_credentials(token_data: Dict[str, Any], user_info: Optional[Dict[str, Any]] = None) -> bool:
    """保存凭证到 accounts.toml（增强版）"""
    try:
        access_token = token_data.get('access_token')

        # 如果没有提供 user_info，尝试获取
        if not user_info and access_token:
            user_info = await get_user_info(access_token)

        # 获取项目信息
        projects = None
        if access_token:
            projects = await get_project_info(access_token)

        # 准备新的账户数据（只保留必要字段）
        new_account = {
            # Token 信息（Antigravity API 必需）
            'access_token': access_token,
            'refresh_token': token_data.get('refresh_token'),

            # 时间戳
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'last_used': time.strftime('%Y-%m-%d %H:%M:%S'),

            # 状态字段（统一使用 disabled）
            'disabled': False,
        }

        # 添加用户信息（只保留必要字段）
        if user_info:
            new_account.update({
                'email': user_info.get('email', ''),
                'user_id': user_info.get('id', ''),
            })
            log.info(f"📧 账户邮箱: {user_info.get('email', 'unknown')}")
            log.info(f"👤 用户ID: {user_info.get('id', 'unknown')}")

        # 添加项目信息
        if projects and len(projects) > 0:
            # 保存项目列表（只保存项目 ID 和名称，避免数据过多）
            project_list = [
                {
                    'project_id': p.get('projectId', ''),
                    'project_name': p.get('name', ''),
                    'project_number': p.get('projectNumber', ''),
                    'state': p.get('lifecycleState', '')
                }
                for p in projects[:10]  # 最多保存前10个项目
            ]
            new_account['projects'] = project_list
            new_account['project_count'] = len(projects)
            log.info(f"📁 关联项目数: {len(projects)} 个")
            if projects:
                log.info(f"📁 首个项目: {projects[0].get('name', 'unknown')} ({projects[0].get('projectId', 'unknown')})")

        # 确保目录存在
        os.makedirs(os.path.dirname(CREDS_FILE), exist_ok=True)

        # 读取现有数据
        existing_data = {}
        if os.path.exists(CREDS_FILE):
            try:
                with open(CREDS_FILE, 'r', encoding='utf-8') as f:
                    existing_data = toml.load(f)
            except Exception as e:
                log.warning(f"Failed to load existing accounts.toml: {e}")

        # 更新数据
        if 'accounts' not in existing_data:
            existing_data['accounts'] = []

        # 检查是否已存在相同邮箱的账户（去重）
        email = new_account.get('email', '')
        if email:
            # 移除相同邮箱的旧账户
            existing_data['accounts'] = [
                acc for acc in existing_data['accounts']
                if acc.get('email', '') != email
            ]
            log.info(f"✨ 已移除邮箱 {email} 的旧凭证（如有）")

        # 添加新账户
        existing_data['accounts'].append(new_account)

        # 写入文件
        with open(CREDS_FILE, 'w', encoding='utf-8') as f:
            toml.dump(existing_data, f)

        log.info(f"✅ 凭证已保存到 {CREDS_FILE}")
        log.info(f"📊 当前共有 {len(existing_data['accounts'])} 个账户")

        # ⚡ 立即加入轮换队列（事件驱动，无需等待轮询）
        try:
            from src.antigravity_credential_manager import get_antigravity_credential_manager

            # 准备账号数据（包含 expires_in 和 timestamp）
            account_data_for_manager = new_account.copy()
            account_data_for_manager['expires_in'] = token_data.get('expires_in', 3600)  # 默认 1 小时
            account_data_for_manager['timestamp'] = int(time.time() * 1000)  # 毫秒时间戳

            antigravity_manager = await get_antigravity_credential_manager()
            await antigravity_manager.add_account(account_data_for_manager)
            log.info(f"[INSTANT] Antigravity 账号 {email} 已立即加入轮换队列")
        except Exception as e:
            log.warning(f"添加到轮换队列失败（不影响保存）: {e}")

        return True
    except Exception as e:
        log.error(f"Failed to save credentials: {e}")
        return False
