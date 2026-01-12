# MioHub Chrome Extension

Save images, text, and URLs directly from any webpage to your MioHub workspace.

## Features

- 📸 **Save Images** - Right-click any image to save it to MioHub as a MioNote
- 📝 **Save Text** - Select text and save it with formatting preserved
- 🔗 **Save URLs** - Bookmark pages directly to your workspace
- 📁 **Auto-Organization** - All content saves to "Web Clippings" folder automatically
- ⚡ **Context Menus** - Quick access from right-click menu
- 🔒 **Secure** - API token authentication with 1-year validity

## Installation

### 1. Generate API Token

1. Log into your MioHub account
2. Go to **Settings → Chrome Extension** (or visit `/extension-settings`)
3. Click **Generate API Token**
4. Copy the generated token (keep it secure!)

### 2. Install Extension

**Option A: Load Unpacked (Development)**

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `chrome_extension` folder
5. The extension icon will appear in your toolbar

**Option B: From ZIP (Production)**

1. Download `chrome_extension.zip` from MioHub
2. Extract the ZIP file
3. Follow steps from Option A above

### 3. Connect Extension

1. Click the MioHub extension icon in your toolbar
2. Enter your MioHub server URL (e.g., `http://localhost:5555` or `https://yourusername.pythonanywhere.com`)
3. Paste your API token
4. Click **Connect to MioHub**
5. Done! ✓

## Usage

### Popup Interface

Click the extension icon to access:

- **Save Current Page URL** - Bookmark the active tab
- **Save Selected Text** - Save highlighted text from the page
- **Save Image from Page** - Interactive image selection (coming soon)

All content automatically saves to the **Web Clippings** folder in your MioHub workspace.

### Context Menu (Right-Click)

Right-click on:

- **Images** → "Save Image to MioHub"
- **Links** → "Save Link to MioHub"
- **Selected Text** → "Save Text to MioHub"
- **Page** → "Save Page URL to MioHub"

## Security

### API Token

- Valid for 1 year from generation
- Stored locally in browser (not synced)
- Can be revoked/regenerated anytime
- **Never share your token!**

### Permissions

The extension requires:

- `activeTab` - Access current tab information
- `storage` - Store settings locally
- `contextMenus` - Add right-click menu options
- `scripting` - Extract selected text from pages

## Configuration

### Server URLs

**Local Development:**
```
http://localhost:5555
```

**PythonAnywhere:**
```
https://yourusername.pythonanywhere.com
```

**Custom Domain:**
```
https://your-domain.com
```

Update `host_permissions` in `manifest.json` for custom servers.

### Web Clippings Folder

All content from the extension saves to a **Web Clippings** folder, which is automatically created in your root folder. This keeps all your saved web content organized in one place.

## File Storage

All content is saved as **MioNote** files:

- **Text** - Formatted as HTML paragraphs with source URL
- **Images** - Embedded with original quality, auto-deduplicated
- **URLs** - Saved as clickable bookmarks with page title

## Troubleshooting

### "Cannot connect to server"

- Verify server URL is correct (no trailing slash)
- Check that MioHub is running
- Ensure firewall allows connection

### "Invalid or expired token"

- Regenerate token in MioHub settings
- Update token in extension
- Check token hasn't expired (1 year validity)

### "Storage quota exceeded"

- Guest users have 50MB limit
- Upgrade account type or free up space
- Contact admin for quota increase

### Images not saving

- Check image is accessible (not blocked by CORS)
- Try smaller images first
- Verify storage quota available

## Development

### File Structure

```
chrome_extension/
├── manifest.json       # Extension configuration
├── popup.html         # Popup UI
├── popup.css          # Popup styles
├── popup.js           # Popup logic
├── background.js      # Service worker (context menus)
├── icons/             # Extension icons
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md          # This file
```

### API Endpoints

- `POST /api/extension/generate-token` - Generate API token
- `POST /api/extension/verify-token` - Verify token validity
- `POST /api/extension/revoke-token` - Revoke token
- `GET /api/extension/folders` - Fetch folder tree
- `POST /api/extension/set-default-folder` - Set default folder
- `POST /api/extension/save-content` - Save content to MioHub

### Testing

1. Make changes to extension files
2. Go to `chrome://extensions/`
3. Click refresh icon on MioHub extension card
4. Test functionality

## Version History

### v1.0.0 (2026-01-06)

- Initial release
- Save images, text, URLs
- Folder selection
- Context menu integration
- API token authentication

## Support

For issues or feature requests:

1. Check troubleshooting section above
2. Visit MioHub documentation
3. Contact support via MioHub settings

## License

Part of the MioHub project. All rights reserved.
