import os
import sys
import requests

def load_key_from_envfile(path='Agent/.env'):
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line=line.strip()
                if line.startswith('ZHIPU_API_KEY='):
                    return line.split('=',1)[1].strip()
    except Exception as e:
        print('无法读取', path, e)
    return None

def main():
    key = load_key_from_envfile()
    if not key:
        print('未找到 ZHIPU_API_KEY，请确认 Agent/.env 中存在该项')
        sys.exit(1)

    url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
    for scheme in ['', 'Bearer ']:
        header = {'Authorization': scheme + key, 'Content-Type': 'application/json'}
        try:
            r = requests.post(url, headers=header, json={'model':'test','messages':[]}, timeout=10)
            print('SCHEME:', '<no-scheme>' if scheme=='' else 'Bearer', 'STATUS:', r.status_code)
            print('BODY:', r.text[:1000])
        except Exception as e:
            print('SCHEME:', '<no-scheme>' if scheme=='' else 'Bearer', 'ERROR:', e)

if __name__ == '__main__':
    main()
