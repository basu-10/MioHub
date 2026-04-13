# ── Portfolio content ────────────────────────────────────────────────────────
# Edit this file to update the portfolio site content.

AUTHOR = {
    "name":   "Asesh Basu",
    "email":  "you@example.com",
    "github": "https://github.com/yourusername",
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
                    "Rich-text notes with autosave",
                    "Infinite canvas whiteboard",
                    "File & folder management",
                    "AI graph workspace",
                    "Chrome extension for quick capture",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Flask", "Python", "MySQL", "Tailwind CSS"],
                "status":   "beta",
                "category": "web",
            },
            {
                "id":          "read-later",
                "name":        "Read Later",
                "tagline":     "Save articles to your personal account — Pocket clone",
                "icon":        "bookmark",
                "description": (
                    "A self-hosted read-later service. Use the browser extension to save "
                    "any article or page to your personal account, then read it anytime."
                ),
                "features": [
                    "Browser extension for one-click saving",
                    "Personal account with private article library",
                    "Article reader view",
                    "Tag & folder organisation",
                ],
                "url":      None,
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
                "id":          "clipboard-history",
                "name":        "Clipboard History",
                "tagline":     "Secure offline clipboard manager protected by password",
                "icon":        "content_paste",
                "description": (
                    "An offline clipboard manager that keeps a searchable history of "
                    "everything you copy, protected by a local password. "
                    "No cloud, no telemetry."
                ),
                "features": [
                    "Persistent clipboard history",
                    "Password-protected access",
                    "Full offline — no cloud sync",
                    "Fast search across history",
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
                "id":          "notekeeper",
                "name":        "NoteKeeper",
                "tagline":     "Notes, folders, tags and fast full-content search",
                "icon":        "edit_note",
                "description": (
                    "Create note files, organise them into folders and tag them. "
                    "A fast search indexes file content, folder names, file names, "
                    "and tags all at once."
                ),
                "features": [
                    "Note files with rich editing",
                    "Folder & tag organisation",
                    "Fast full-content search",
                    "Search across names, folders, tags",
                    "Windows & sysvinit Linux",
                ],
                "url":      None,
                "download": None,
                "github":   None,
                "tech":     ["Python", "PyQt"],
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
