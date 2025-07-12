import os
import ssl

# 请求头配置
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    'Cookie': 'Hm_lvt_7fdef555dc32f7d31fadd14999021b7b=1743995269; HMACCOUNT=7684B2F2E92F5605; notice=202547; cleanMode=0; Hm_lpvt_7fdef555dc32f7d31fadd14999021b7b=1743995601'
}

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'data', 'search_cache')

# SSL配置
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE