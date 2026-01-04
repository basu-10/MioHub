from datetime import datetime
import os

# Configuration - add to your app setup
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'images')
# Dedicated PDF storage (mirrors image path pattern for reuse across products)
PDF_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'pdfs')
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}

# get current time string for default titles
now=datetime.now().strftime("%Y-%m-%d %H:%M:%S").replace(" ",".")
