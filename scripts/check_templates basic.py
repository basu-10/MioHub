import sys
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, TemplateError
from pathlib import Path

TEMPLATES_PATH = Path(__file__).resolve().parents[1] / 'blueprints' / 'p2' / 'templates'

env = Environment(loader=FileSystemLoader(str(TEMPLATES_PATH)))

templates_to_check = [
    'p2/folder_view.html',
]

errors = False
for t in templates_to_check:
    try:
        env.get_template(t)
        print(f"OK: {t}")
    except TemplateSyntaxError as e:
        errors = True
        print(f"SYNTAX ERROR in {t}: {e.message} (line {e.lineno})")
    except TemplateError as e:
        errors = True
        print(f"TEMPLATE ERROR in {t}: {e}")

if errors:
    sys.exit(2)
else:
    sys.exit(0)
