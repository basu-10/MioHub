import requests, io

s = requests.Session()
base='http://127.0.0.1:5555'
login_url=base+'/login'
resp=s.post(login_url, data={'username':'testuser','password':'password123'})
print('Login', resp.status_code)
# Prepare a tiny PNG-ish file for upload
png= b'\x89PNG\r\n\x1a\n' + b'\x00'*2048
files=[('files', ('test.png', io.BytesIO(png), 'image/png'))]
resp=s.post(base+'/assets/upload', files=files)
print('Upload status', resp.status_code)
try:
    print(resp.json())
except Exception as e:
    print('No JSON', e)
    print(resp.text[:400])
