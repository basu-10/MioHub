# Icon Placeholder

The extension needs three icon sizes:

- `icon16.png` - 16x16 pixels (toolbar)
- `icon48.png` - 48x48 pixels (extension management)
- `icon128.png` - 128x128 pixels (Chrome Web Store)

## Create Icons

You can create simple icons using any image editor. Recommended design:

- Background: Dark (#0a0a0b or transparent)
- Icon: Teal (#14b8a6)
- Shape: Bookmark/folder/document symbol
- Style: Minimal, flat design

## Quick Icon Generation

Use an online tool like:
- https://favicon.io/
- https://realfavicongenerator.net/
- Canva
- Figma

Or create with code (Python + Pillow):

```python
from PIL import Image, ImageDraw

def create_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw rounded rectangle (bookmark shape)
    margin = size // 8
    draw.rounded_rectangle(
        [(margin, margin), (size - margin, size - margin)],
        radius=size // 8,
        fill='#14b8a6'
    )
    
    return img

# Generate icons
create_icon(16).save('icon16.png')
create_icon(48).save('icon48.png')
create_icon(128).save('icon128.png')
```

## Temporary Workaround

Until you create custom icons, you can:

1. Use placeholder colored squares
2. Copy icons from another extension
3. Download free icons from https://icons8.com or https://iconmonstr.com

The extension will work without icons, but Chrome will show a default puzzle piece icon.
