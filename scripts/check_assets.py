import requests
s = requests.Session()
login_url = 'http://127.0.0.1:5555/login'
resp = s.post(login_url, data={'username':'testuser', 'password':'password123'})
print('Login status', resp.status_code)
r = s.get('http://127.0.0.1:5555/assets')
print('Assets status', r.status_code)
print('Contains Find unused?', 'Find unused' in r.text)
print('Contains btnFindUnused?', 'btnFindUnused' in r.text)
print('Contains Delete all unused?', 'Delete all unused' in r.text)
open('scripts/assets_page.html', 'w', encoding='utf-8').write(r.text)
print('Wrote scripts/assets_page.html')
