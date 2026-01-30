import toml
import shutil
from datetime import datetime

# 备份原文件
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_name = f'creds/accounts_{timestamp}.toml.bak'
shutil.copy('creds/accounts.toml', backup_name)
print(f'Backup created: {backup_name}')

# 读取文件
data = toml.load('creds/accounts.toml')
original_count = len(data['accounts'])

# 过滤掉没有 user_id 或 email 的账号
valid_accounts = [a for a in data['accounts'] if a.get('user_id') and a.get('email')]
removed_count = original_count - len(valid_accounts)

# 保存
data['accounts'] = valid_accounts
with open('creds/accounts.toml', 'w', encoding='utf-8') as f:
    toml.dump(data, f)

print(f'Cleaned: removed {removed_count} invalid accounts')
print(f'Remaining: {len(valid_accounts)} valid accounts')
