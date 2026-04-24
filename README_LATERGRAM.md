# LaterGram

LaterGram serves as the specialized read-later and web-clipping component of the MioHub ecosystem, offering several advantages over mainstream "big brand" alternatives by focusing on deep integration and smarter data management.


## Why use LaterGram instead of typical clippers?
### It doesn’t create another junk drawer
Most tools (like Pocket or Instapaper) dump everything into their own silo.
LaterGram writes directly into your existing workspace structure. Your research lands exactly where it belongs. 
### Security isn’t an afterthought
No “store your password and hope for the best.”
It uses revocable tokens. You can kill access anytime. That’s how extensions should’ve been built from day one. 
### Capture → read → use, all in one place
You don’t clip in one app and process in another. There’s a dedicated reading surface inside the same system, so nothing gets lost between steps. 
### Flexible capture without noise
Text, images, full pages, cleaned pages—it handles all of it without forcing you into one format. 

## Where it beats big tools
### No silo problem
Everything goes into the same structure as your notes and projects. No syncing, no exporting, no duplication gymnastics. 
### Less garbage, more signal
Instead of endless duplicate links, it normalizes URLs and groups related content.
That alone fixes the “saved 500 things, used 3” problem. 
### File it correctly upfront
Most clippers dump into an “Inbox” you never clean.
Here, you choose the destination at capture time. Organization isn’t deferred—it’s enforced. 
### You control access, not the extension
Token-based access means the browser isn’t holding permanent keys to your data. You decide when it can talk to your system. 

## What It Does

- Clips text, images, URLs, and cleaned page content from the browser.
- Groups related content by source URL to reduce duplication.
- Lets users choose destination folders from their workspace hierarchy.
- Uses revocable API tokens instead of storing account passwords in the extension.
- Provides a dedicated in-app reading surface for saved clippings.

## Main Workflow

1. A logged-in user opens the extension settings page in MioHub.
2. The server generates or regenerates an API token for extension access.
3. The browser extension stores the server URL and token locally.
4. The extension verifies the token before showing save actions.
5. Save actions send content to the extension API.
6. The server stores or appends the content inside the user's clipping hierarchy.

## Save Types

- Text selections
- Images
- URLs
- Clean-page captures

## Key Product Behaviors

### Smart Grouping

LaterGram normalizes source URLs so multiple clips from the same site or page can stay grouped together instead of producing unnecessary duplicate entries.

### Folder Integration

Users can browse folder trees, set default save locations, and route captures into the broader MioSpace hierarchy.

### Token-Based Security

Extension requests use bearer tokens. Tokens can be generated, regenerated, revoked, and expire automatically.

## Where It Lives In This Repo

- Product routes: `blueprints/p5/routes.py`
- Extension API: `blueprints/p5/extension_api.py`
- Reading UI: `blueprints/p5/templates/p5/extension_home.html`
- Extension settings UI: `blueprints/p5/templates/p5/extension_settings.html`
- Chrome extension client: `miohub_chrome_extension/`
- Flow documentation: `docs/LATERGRAM_FLOW.md`

## Main Entry Points

- Settings page: `/extension-settings`
- Reading home: `/extension-home`
- Clean-page save route: `/save-clean-page`
- Extension package download route: `/download-chrome-extension`

## API Surface

The extension API supports token lifecycle management, folder retrieval, default-folder selection, token verification, and content-saving requests.

Key endpoint families:

- Token generation and revocation
- Token verification
- Folder tree retrieval
- Default folder selection
- Content saving for extension actions
- LaterGram-specific folder creation, deletion, and clip moves

## Relationship To MioSpace

LaterGram is not a separate storage system. It saves captured content into the user's MioHub workspace and uses the MioSpace folder structure as its organizing model.

## Recommended Reading

- Root project overview: `README.md`
- MioSpace product doc: `README_MIOSPACE.md`
- Detailed flow and endpoint notes: `docs/LATERGRAM_FLOW.md`
- Extension packaging notes: `miohub_chrome_extension/README.md`
