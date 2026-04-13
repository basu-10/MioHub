# ── Portfolio content ────────────────────────────────────────────────────────
# Edit this file to update the portfolio site content.

AUTHOR = {
    "name":   "Asesh Basu",
    "email":  "asesh.basu.dev@gmail.com",
    "github": "https://github.com/basu-10",
    "bio":    "Developer and maker. I build tools that solve real problems.",
}

# Each section appears as a filter tab on the landing page.
# The first section whose layout == "featured" provides the hero banner product.
SECTIONS = [
    # ── Webapps / Websites ───────────────────────────────────────────────────
    {
        "label":  "Webapps",
        "layout": "featured",   # first section with layout="featured" → hero banner
        "products": [
            {
                "id":          "miohub",
                "name":        "MioHub",
                "tagline":     "Personal productivity platform",
                "icon":        "hub",
                "description": (
                    "A personal productivity platform with notes, whiteboards, "
                    "file management, and an AI-powered graph workspace."
                ),
                "features": [
                    "Hierarchical folders with breadcrumbs and batch actions",
                    "MioWord rich documents with markdown, HTML, and autosave",
                    "MioBoard canvas whiteboards saved as structured JSON",
                    "Per-item sharing, public links, and quota-aware permissions",
                ],
                "url":      "/dashboard",
                "download": None,
                "github":   "https://github.com/basu-10/MioHub",
                "tech":     ["Flask", "Python", "MySQL", "Tailwind CSS"],
                "status":   "beta",
                "category": "web",
            },
            {
                "id":          "read-later",
                "name":        "LaterGram",
                "tagline":     "Read later with smart web clipping and folder integration",
                "icon":        "bookmark",
                "description": (
                    "LaterGram brings read-later power to MioHub. Save text, images, "
                    "links, and full pages from the browser extension into your folder-based workspace."
                ),
                "features": [
                    "One-click web clipping for text, images, links, and pages",
                    "Smart URL grouping keeps content from the same site together",
                    "Choose destination folders from your MioSpace hierarchy",
                    "Right-click context menu actions for fast capture",
                    "Secure API token authentication with revocable access",
                ],
                "url":      "/extension-home",
                "download": None,
                "github":   None,
                "tech":     ["Flask", "Python", "JavaScript"],
                "status":   "beta",
                "category": "web",
            },
            {
                "id":          "chatbot",
                "name":        "Chatbot",
                "tagline":     "Private AI chat using your own API key",
                "icon":        "smart_toy",
                "description": (
                    "Connect your Groq or Anthropic API key and start chatting privately. "
                    "No data leaves your own infrastructure."
                ),
                "features": [
                    "Supports Groq and Anthropic providers",
                    "Conversations stay private",
                    "Bring your own API key",
                    "Clean chat interface",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Flask", "Python", "Tailwind CSS"],
                "status":   "beta",
                "category": "web",
            },
        ],
    },

    # ── Dev Tools ────────────────────────────────────────────────────────────
    {
        "label":  "Dev",
        "layout": "list",
        "products": [
            {
                "id":          "llm-batch-tester",
                "name":        "LLM Batch Tester",
                "tagline":     "Test one prompt across multiple models side-by-side",
                "icon":        "science",
                "description": (
                    "Enter a prompt, select multiple models, and compare their responses "
                    "in one view. Supports local Ollama / LM Studio instances and online "
                    "providers like Groq. Includes prompt management for running multiple "
                    "prompts per model."
                ),
                "features": [
                    "Single prompt → multiple model responses",
                    "Prompt library & management",
                    "Connect to local Ollama or LM Studio",
                    "Online providers: Groq and more",
                    "Side-by-side diff view",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Python", "Flask", "Tailwind CSS"],
                "status":   "beta",
                "category": "dev",
            },
            {
                "id":          "terminal-tool",
                "name":        "Terminal Tool",
                "tagline":     "Modular CLI utilities for everyday dev tasks",
                "icon":        "terminal",
                "description": (
                    "A modular command-line toolkit covering file operations, "
                    "database search, system diagnostics, and upload helpers — "
                    "all from a single entry point."
                ),
                "features": [
                    "File operations module",
                    "Database search & query helpers",
                    "System diagnostics",
                    "Upload helpers",
                    "Modular — add your own commands",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Python"],
                "status":   "stable",
                "category": "dev",
            },
        ],
    },

    # ── Fun ──────────────────────────────────────────────────────────────────
    {
        "label":  "Fun",
        "layout": "list",
        "products": [
            {
                "id":          "uno-clone",
                "name":        "UNO Clone",
                "tagline":     "Real-time multiplayer UNO for up to 4 players",
                "icon":        "casino",
                "description": (
                    "A WebSocket-based UNO implementation for up to 4 players. "
                    "Real-time game state sync — no polling."
                ),
                "features": [
                    "Up to 4 players per room",
                    "Real-time via WebSockets",
                    "Full UNO rule set",
                    "Room creation & joining",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Flask", "Socket.IO", "JavaScript"],
                "status":   "beta",
                "category": "fun",
            },
        ],
    },

    # ── Cross-platform Desktop Apps ──────────────────────────────────────────
    {
        "label":  "Desktop",
        "layout": "list",
        "products": [
            {
                "id":          "spotlight-clone",
                "name":        "Spotlight Clone",
                "tagline":     "Fast launcher with file search, app search & inline math",
                "icon":        "search",
                "description": (
                    "A cross-platform launcher (Windows & sysvinit Linux) that indexes "
                    "files and installed software for instant search, triggers internet "
                    "searches, and evaluates math expressions inline."
                ),
                "features": [
                    "Indexed file & installed-app search",
                    "Trigger internet search",
                    "Inline math result as you type",
                    "Windows & sysvinit Linux",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Python", "PyQt"],
                "status":   "stable",
                "category": "desktop",
            },
            {
                "id":          "cliplogger",
                "name":        "ClipLogger",
                "tagline":     "Windows clipboard history manager with text and image support",
                "icon":        "content_paste",
                "description": (
                    "ClipLogger is a Windows clipboard history manager built with Python "
                    "and PySide6. It captures text and image clipboard data, stores it "
                    "locally in SQLite, and provides a desktop UI for browsing, pinning, "
                    "editing, deleting, and exporting clipboard items."
                ),
                "features": [
                    "Clipboard history capture for text and image data",
                    "Persistent SQLite storage under %LOCALAPPDATA%\\ABasu_apps\\ClipLogger\\",
                    "Main history list with multi-select support",
                    "Image gallery view for clipboard image entries",
                    "Preview panel with text editing and image viewing",
                    "Pin/unpin favorites to prevent auto-pruning",
                    "Delete selected clipboard history safely",
                    "Export selected items to Microsoft Word (.docx)",
                    "Light/dark theme support",
                    "Optional Windows auto-start setting",
                    "System tray integration with hide/minimize behavior",
                ],
                "url":      None,
                "download": "https://github.com/basu-10/ClipLogger/releases/download/stable/ClipLogger-Setup-1.6.3.exe",
                "github":   "https://github.com/basu-10/ClipLogger",
                "tech":     ["Python", "PySide6"],
                "status":   "stable",
                "category": "desktop",
            },
            {
                "id":          "landrop",
                "name":        "LanDrop",
                "tagline":     "LAN file sharing — start a server, any device can drop files",
                "icon":        "wifi_tethering",
                "description": (
                    "Run this program on any machine in a LAN. Other devices on the same "
                    "network can then exchange files with it via a browser — no installation "
                    "needed on the sender's side."
                ),
                "features": [
                    "Zero-setup receiver (browser-based sender)",
                    "Works across OS boundaries",
                    "LAN-only — stays off the internet",
                    "Windows & sysvinit Linux",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Python", "Flask"],
                "status":   "stable",
                "category": "desktop",
            },
            {
                "id":          "notestack",
                "name":        "NoteStack",
                "tagline":     "Smart desktop notes with folders, tags, search and filters",
                "icon":        "sticky_note_2",
                "description": (
                    "A desktop note manager with folders, tags, favourites, full-text search, "
                    "and a responsive PyQt6 interface that stores data per-user on each OS."
                ),
                "features": [
                    "Folders — create, rename, and delete folders; assign notes to folders; filter the sidebar by folder",
                    "Tags — add arbitrary tags with autocomplete, counts, and click-to-filter support",
                    "Favorites — star or un-star notes from any view, plus a dedicated favorites section",
                    "Quick search and advanced search modal with keyword input, multi-tag selection, and clear-all",
                    "Sort by newest first, oldest first, A→Z, or Z→A; switch between grid and list views",
                    "Note detail modal shows full content, folder/date metadata, copy-to-clipboard and edit buttons",
                    "Responsive high-DPI PyQt6 UI with per-user OS-specific application data storage",
                ],
                "url":      None,
                "download": "https://github.com/basu-10/NoteStack/blob/main/.releases/NoteStack-Setup-1.6.4.exe",
                "github":   "https://github.com/basu-10/NoteStack",
                "tech":     ["Python", "PyQt6"],
                "status":   "stable",
                "category": "desktop",
            },
        ],
    },

    # ── Experimental ─────────────────────────────────────────────────────────
    {
        "label":  "Experimental",
        "layout": "list",
        "products": [
            {
                "id":          "png-to-gif",
                "name":        "PNG to GIF",
                "tagline":     "Turn a spritesheet into an animated GIF",
                "icon":        "gif_box",
                "description": (
                    "Asset management utility: slice a spritesheet PNG into frames "
                    "and export as an animated GIF."
                ),
                "features": [
                    "Configurable frame size & rate",
                    "Preview before export",
                    "Could become a webapp",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Python", "Pillow"],
                "status":   "alpha",
                "category": "experimental",
            },
            {
                "id":          "gifs-to-gif",
                "name":        "GIFs to GIF",
                "tagline":     "Combine start, loop, and end animations into one GIF",
                "icon":        "animation",
                "description": (
                    "Merge multiple GIF clips (intro → loop → outro) into a single "
                    "composed animation."
                ),
                "features": [
                    "Start / loop / end clip composition",
                    "Frame-level control",
                    "Could become a webapp",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Python", "Pillow"],
                "status":   "alpha",
                "category": "experimental",
            },
            {
                "id":          "text-to-image",
                "name":        "Text to Image",
                "tagline":     "Place text on a background and export as an image",
                "icon":        "text_fields",
                "description": (
                    "Quick social-post tool: pick a background, type your text, "
                    "and get a ready-to-share image. No design skills needed."
                ),
                "features": [
                    "Background picker",
                    "Typography controls",
                    "Export as PNG / JPG",
                    "Could become a webapp",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Python", "Pillow"],
                "status":   "alpha",
                "category": "experimental",
            },
            {
                "id":          "images-to-image",
                "name":        "Images to Image",
                "tagline":     "Collage maker — combine images and text into one image",
                "icon":        "photo_library",
                "description": (
                    "Arrange multiple images and optional text overlays into a single "
                    "composited image. Ideal for quick social posts."
                ),
                "features": [
                    "Drag-and-drop layout",
                    "Text overlay support",
                    "Export as PNG / JPG",
                    "Could become a webapp",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Python", "Pillow"],
                "status":   "alpha",
                "category": "experimental",
            },
        ],
    },
]
