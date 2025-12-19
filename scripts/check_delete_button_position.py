import requests
s=requests.Session()
base='http://127.0.0.1:5555'
login_url=base+'/login'
resp=s.post(login_url, data={'username':'testuser','password':'password123'})
print('Login', resp.status_code)
resp=s.get(base+'/assets')
html=resp.text
res_pos=html.find('Reserve (<span class="reserve-count"')
btn_pos=html.find('id="btnDeleteUnused"')
reserveGrid_pos=html.find('id="reserveGrid"')
print('Reserve header idx', res_pos)
print('Btn idx', btn_pos)
print('Reserve grid idx', reserveGrid_pos)
if res_pos==-1 or btn_pos==-1 or reserveGrid_pos==-1:
    print('Missing elements?')
else:
    if res_pos < btn_pos < reserveGrid_pos:
        print('Button appears between reserve header and reserve grid — good')
    else:
        print('Button not in expected position')
# Also check header area (first 300 chars) for the button
print('Btn in top header?', 'id="btnDeleteUnused"' in html[:300])
