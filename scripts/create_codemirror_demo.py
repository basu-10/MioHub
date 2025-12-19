"""
Create a CodeMirror demo file in the database under root/demos

This script creates a folder called 'demos' under the root folder for
`testuser` (created by init_db.py). It then creates a `code` type file
with illustrative multi-language samples to demonstrate CodeMirror modes.

Run: python scripts/create_codemirror_demo.py
"""

from flask import Flask
from extensions import db
from blueprints.p2.models import File, Folder, User
import config
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

DEMO_CONTENT = '''# CodeMirror Demo — All Languages

This demo file contains short examples across several languages to let you
try out CodeMirror modes from the Editor dropdown (top-right).</n
Instructions:
1. Open this file in the Code Editor.
2. Select a language from the "Language" dropdown to highlight the current
   content according to that language's mode.
3. Use Ctrl+S to save and Ctrl+F to search, line numbers, selection, and
   CodeMirror's features like bracket matching and active-line highlighting.

---

## Python — Example
```python
# Fibonacci with recursion and simple caching
from functools import lru_cache

@lru_cache(maxsize=128)
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n-1) + fib(n-2)

print([fib(i) for i in range(10)])
```

---

## JavaScript — Example
```javascript
// JavaScript async/await and fetch
async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error('Network error');
  return r.json();
}

fetchJson('/api/ping').then(console.log).catch(console.error);
```

---

## TypeScript — Example
```typescript
interface User { id: number; name: string; email?: string }
const users: User[] = [];
function addUser(u: User){ users.push(u); }
```

---

## Java — Example
```java
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello from Java");
    }
}
```

---

## C++ — Example
```cpp
#include <iostream>
#include <vector>
template <typename T>
T sum(const std::vector<T>& a) {
    T total{};
    for (auto &x : a) total += x;
    return total;
}

int main(){ std::cout<<sum(std::vector<int>{1,2,3})<<"\n"; }
```

---

## SQL — Example
```sql
WITH totals AS (
  SELECT owner_id, COUNT(*) AS total_files
  FROM files
  GROUP BY owner_id
)
SELECT u.username, t.total_files
FROM user u
LEFT JOIN totals t ON t.owner_id = u.id
ORDER BY t.total_files DESC;
```

---

## HTML & CSS — Example
```html
<!doctype html>
<html>
<head>
  <style>
    body { font-family: system-ui; background: #0f1720; color: #e6f6f5 }
    .demo { padding: 1rem; }
  </style>
</head>
<body>
  <div class="demo"><h3>HTML Demo</h3></div>
</body>
</html>
```

---

## JSON & YAML — Example
```json
{"name": "codemirror-demo", "version": "1.0.0", "languages": ["py", "js", "java"]}
```

```yaml
name: codemirror-demo
languages:
  - python
  - javascript
  - java
```

---

## Shell — Example
```bash
# simple shell script
for f in *.py; do echo "found $f"; done
```

---

That's it — you can switch the language in the editor to compare how CodeMirror
highlights the file. When done, try copying, downloading or editing to see
features such as bracket match, line numbers and key-bindings.
'''


def create_demo():
    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        if not user:
            print('❌ Error: testuser not found. Run init_db.py to create demo users.')
            return

        root = Folder.query.filter_by(user_id=user.id, parent_id=None).first()
        if not root:
            print('❌ Error: Root folder not found for testuser.')
            return

        # Create 'demos' folder if it doesn't exist
        demo_folder = Folder.query.filter_by(user_id=user.id, parent_id=root.id, name='demos').first()
        if not demo_folder:
            demo_folder = Folder(user_id=user.id, parent_id=root.id, name='demos', description='Demo folder for CodeMirror showcase')
            db.session.add(demo_folder)
            db.session.commit()
            print('✓ Created folder: demos')
        else:
            print('✓ Found existing folder: demos')

        # Create demo code file
        existing = File.query.filter_by(owner_id=user.id, folder_id=demo_folder.id, title='CodeMirror Demo - All Languages').first()
        if existing:
            print(f"ℹ️ Demo file already exists: ID {existing.id}")
            return

        demo_file = File(
            owner_id=user.id,
            folder_id=demo_folder.id,
            type='code',
            title='CodeMirror Demo - All Languages',
            content_text=DEMO_CONTENT,
            metadata_json={'description':'Multi-language CodeMirror demonstration', 'language': 'plaintext'},
            is_public=True
        )
        db.session.add(demo_file)
        db.session.commit()

        print('✅ Created demo file: CodeMirror Demo - All Languages')
        print(f'   File ID: {demo_file.id}')
        print('📂 Path: root/demos')


if __name__ == '__main__':
    create_demo()
