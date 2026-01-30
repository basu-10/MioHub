# LaterGram (Read Later) — Flow & Endpoints 📘

This document describes the LaterGram (Read Later) flow used by MioHub's Chrome extension and server. It explains how the API key (token) is created, how it is inserted and persisted in the extension, what user-facing options are presented, and which server endpoints are called for each action. No code is included — only the components, data shapes, and flows.

---

## Overview

- **Actors**: User (logged-in), Web UI (MioHub site), Chrome Extension (popup/background), Server API (Extension API endpoints).
- **Goal**: Allow a logged-in user to generate an API token in the site UI, configure the extension with server URL + token, and save page/selection/cleaned pages back to the user's Web Clippings folder.

---

## Key Concepts (atomic data)

- API Token: a secure random token (generated server-side, e.g., token_urlsafe with ~32 bytes of entropy). It is returned in responses and **expires after 365 days**.
- Authorization header: all extension-to-server requests use `Authorization: Bearer <token>`.
- `serverUrl`: base URL of the MioHub server (no trailing slash recommended).
- Storage in extension: uses `chrome.storage.local` keys such as `serverUrl`, `apiToken`, `currentUser` for persistence.
- Save types: `text`, `image`, `url`, `clean-page`.
- Folder selection: extension can fetch user's folder tree and optionally set a default folder for saves.

---

## Where the UX lives (important files)

- Site token generation & settings view: `blueprints/p5/routes.py` -> `extension_settings()` (renders the settings page) and template `blueprints/p5/templates/p5/extension_settings.html` (UI: generate/regenerate/revoke tokens).
- Extension code (client): `chrome_extension/popup.js` (loads settings, stores token, shows options, sends requests), `chrome_extension/popup.html` (UI elements).
- Server endpoints and logic: `blueprints/p5/extension_api.py` (token lifecycle, folder & content save logic).
- In-site Reading UI: `blueprints/p5/routes.py` -> `extension_home()` (reading-style home for clippings).

---

## Step-by-step flow

1. User visits the site and navigates to the Chrome extension settings page (`/extension-settings`).
   - UI presents options to **Generate**, **Regenerate**, or **Revoke** an API token.
   - When the user **generates** a token, the site calls the server function to create a token and sets an expiration of 365 days.

2. User opens the Chrome extension popup and enters the **Server URL** and **API Token** (or the extension may read them from `chrome.storage.local` if previously saved). The extension persists these values to `chrome.storage.local`.
   - The extension always trims the base URL (no trailing slash) and stores `serverUrl`, `apiToken`, and `currentUser`.

3. On popup load the extension attempts to validate authentication by calling the server's token-verify endpoint with the header `Authorization: Bearer <token>`.
   - If the token is valid and not expired, the server returns user metadata and the extension shows its main UI and the username.
   - If invalid/expired, the extension shows the login/auth section and prompts the user to reconnect.

4. The extension UI presents immediate actions (common options shown to the user each time it opens):
   - **Save Page / Save URL** → saves the current tab URL and a link/title.
   - **Save Selection / Save Text** → extracts selection from the page and saves as text.
   - **Save Clean Page** → extracts a cleaned version of the page (the extension collects article content + converts inline images to data URIs) and submits as `clean-page`.

5. When the user clicks a save action, the extension collects the data (selected text, active tab URL/title, or clean-page markdown with embedded data URIs for images) and sends a payload to the server via the content-saving endpoint, including the `Authorization: Bearer <token>` header.

6. Server-side behavior for saves:
   - The server normalizes the source URL to support smart grouping (so multiple clips from the same URL are appended to the same MioNote rather than creating duplicates).
   - For `image` and `clean-page` types, images embedded as data URIs are decoded, stored, and deduplicated; quota checks are performed (especially for guest users).
   - The server either creates a new file or appends to an existing file (updates `clip_count` and `metadata_json`), commits the file, and returns a success JSON response with metadata about the created/updated file.

7. The extension displays success/error feedback to the user and may update local UI (e.g., 'Saved!' or show an error message if saving failed).

---

## Relevant Endpoints (no code; shapes & fields)

- POST `/api/extension/generate-token`
  - Purpose: Generate or regenerate a user's API token (requires site session/auth).
  - Response contains: `token`, `expires`, `user` fields.

- POST `/api/extension/verify-token`
  - Purpose: Verify a token sent by the extension.
  - Request: `Authorization: Bearer <token>`
  - Response: `{ valid: boolean, user: { id, username, user_type, total_data_size } }` on success.

- POST `/api/extension/revoke-token`
  - Purpose: Revoke the current user's token (invalidates extension access).

- GET `/api/extension/folders`
  - Purpose: Return user's folder tree for folder selection in the extension.
  - Response includes: `folders` (tree), `default_folder_id`, `root_folder_id`.

- POST `/api/extension/set-default-folder`
  - Purpose: Set the user's preferred default folder for extension saves.
  - Body: `{ folder_id: <int> }`.

- POST `/api/extension/save-content`
  - Purpose: Save content (text, url, image, clean-page) from the extension.
  - Request header: `Authorization: Bearer <token>`
  - Body fields (typical):
    - `type`: one of `text | image | url | clean-page`
    - `content`: actual payload (text body, data URI image, URL string, or markdown HTML for clean-page)
    - `title`: optional title
    - `folder_id`: optional folder override
    - `url`: optional source URL (context)
    - `page_title`: optional page title
    - `page_description`: optional
  - Response: success boolean, message, and `file` metadata (id, title, type, folder_name, is_new, clip_count, timestamps).

- POST `/save-clean-page` (site-side proxy)
  - Purpose: Allows users to save a clean/processed page using the site session (used when saving via in-site modal rather than extension). It proxies a content fetch service and saves the result to the user's clippings.

- Site UI reading endpoint: `GET /extension-home`
  - Purpose: Display reading-style home for a user's saved clippings (pagination, previews, stats).

---

## Security & Edge Cases ⚠️

- Tokens expire after 365 days; revoke/regenerate flows allow user control.
- Tokens stored locally in the extension (via `chrome.storage.local`) should be treated with the same care as a password — revocation immediately disables extension access.
- For large embedded images, the extension avoids sending massive binaries (client also filters by size) and the server performs quota checks (guests are limited and can be blocked).
- The server validates authorization on all protected endpoints and returns 401/403 responses for missing/expired tokens or quota violations.

---

## UX Notes & Typical Messages

- On first open or invalid token: extension shows **Connect** UI and prompts for Server URL + API token.
- On successful verification: shows the username and the main save options (Save URL, Save Selection, Save Clean Page).
- On any save action: extension shows a loading state and a toast message on success or error.

---

## Quick Reference: Typical request/response fields (not code)

- Auth header: `Authorization: Bearer <api_token>`
- `generate-token` response: `{ success: true, token: "<token>", expires: "YYYY-mm-dd HH:MM:SS", user: { username } }`
- `verify-token` response: `{ valid: true, user: { id, username, total_data_size } }`
- `save-content` body (example fields): `{ type, content, title, folder_id, url, page_title }`
- `save-content` success: `{ success: true, message, file: { id, title, folder_name, is_new, clip_count, created_at, last_modified } }`

---

## Where to look in the codebase

- `blueprints/p5/extension_api.py` — **Server endpoints & saving logic** (token lifecycle, folder logic, `save_content` behavior).
- `blueprints/p5/routes.py` — `extension_settings()`, `extension_home()`, `save_clean_page_from_modal()`.
- `blueprints/p5/templates/p5/extension_settings.html` — UI for generate/regenerate/revoke token actions (client-side triggers that call endpoints).
- `chrome_extension/popup.js` — **Client flow**: persistence, verify-token call on load, save actions, extraction logic for `clean-page` (images → data URIs), and calls to `/api/extension/save-content`.

---

