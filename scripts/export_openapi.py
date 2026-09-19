import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.main import app

def export_schema():
    schema = app.openapi()
    with open('openapi.json', 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2)
    print('Exported openapi.json successfully')

if __name__ == '__main__':
    export_schema()
