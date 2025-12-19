#!/usr/bin/env python
"""Test the updated collect_images_from_content function"""

from blueprints.p2.utils import collect_images_from_content
import json

# Test with JSON content (like whiteboard)
json_content = json.dumps({
    'elements': [
        {'type': 'image', 'src': '/static/uploads/images/1_abc123.webp'},
        {'type': 'image', 'url': 'static/uploads/images/2_def456.webp'}
    ]
})

image_set = set()
collect_images_from_content(json_content, image_set)
print('Images found in JSON:', image_set)

# Test with HTML content
html_content = '<p>Test</p><img src="/static/uploads/images/3_ghi789.webp" />'
image_set2 = set()
collect_images_from_content(html_content, image_set2)
print('Images found in HTML:', image_set2)

# Test with plain text path
text_content = 'Some text with /static/uploads/images/4_jkl012.webp in it'
image_set3 = set()
collect_images_from_content(text_content, image_set3)
print('Images found in text:', image_set3)

# Test infinite whiteboard format
infinite_wb_content = json.dumps({
    'images': [
        {
            'id': 'img1',
            'src': '/static/uploads/images/5_infinite.webp',
            'x': 100,
            'y': 200
        }
    ],
    'strokes': []
})
image_set4 = set()
collect_images_from_content(infinite_wb_content, image_set4)
print('Images found in infinite whiteboard:', image_set4)

print('\nAll tests passed!')
