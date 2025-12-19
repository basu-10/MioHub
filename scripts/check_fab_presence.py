import requests
s=requests.Session()
base='http://127.0.0.1:5555'
login_url=base+'/login'
resp=s.post(login_url, data={'username':'testuser','password':'password123'})
print('Login', resp.status_code)
for path in ['/assets', '/dashboard', '/folders/1']:
    r=s.get(base+path)
    print(path, r.status_code, 'createBtn present?', 'id="createBtn"' in r.text)
    # Save snippets for manual inspection
    open('scripts/check_'+path.strip('/').replace('/','_')+'.html','w', encoding='utf-8').write(r.text)
