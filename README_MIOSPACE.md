# MioSpace

## Why use MioSpace instead of big-brand stacks?

### One system, not ten glued together
Big tools split everything—files, docs, whiteboards. MioSpace puts them in one hierarchy. Documents, canvases, uploads—all live in the same structure. No jumping between apps, no mental context switching. 
### Research goes where the work is
Clipping tools usually dump stuff into a separate bucket you forget about. Here, captures land directly inside your workspace. Research isn’t passive storage—it’s immediately part of the project. 
### Security that isn’t sloppy
Instead of “trust us with everything,” it uses revocable tokens. You can cut access anytime. That’s basic hygiene most big ecosystems still get wrong. 
### Private by default, public when needed
Same system works as a personal vault and a publishing tool. You decide what gets exposed—at the item level. 

## Where it actually beats big players

### No silos
Everything—chat outputs, notes, clips—uses the same structure and backend. No syncing hacks, no duplication. 
### Less garbage accumulation
Web clips are deduplicated and grouped by source. That alone solves the “infinite unread pile” problem most tools create. 
### Visual work isn’t disposable
Whiteboards aren’t screenshots or dead exports. They’re structured data (JSON), so they stay editable, searchable, and reusable. 
### Fast because it’s not bloated
Leans on local-first ideas. Less network dependency, lower latency, more responsiveness. Simple architecture wins here.


## What It Does

- Organizes content with nested folders, breadcrumbs, and batch actions.
- Supports rich document workflows through MioWord editing and previews.
- Supports canvas-style whiteboards through MioBoard.
- Stores files and structured content in a single workspace model.
- Supports public sharing, per-item visibility, and quota-aware permissions.

## Core Capabilities

### Workspace Structure

MioSpace is built around hierarchical folders so users can organize notes, boards, uploads, and generated content in a single tree. The interface emphasizes breadcrumbs, batch operations, and quick navigation for larger libraries.

### Document Editing

MioWord-style documents support markdown and rich HTML editing, autosave flows, and quick previews. The goal is to handle both lightweight notes and larger long-form documents without leaving the workspace.

### Whiteboards And Visual Work

MioBoard adds canvas-style boards for diagrams, sketches, and multi-page visual work. Boards are stored as structured JSON so they can be replayed, edited, and exported consistently.

### Sharing And Access Control

MioSpace supports item-level visibility, public links, and guest-aware quotas. That lets the workspace act as both a private personal space and a controlled publishing surface for selected folders or files.

## Where It Lives In This Repo

- Main blueprint: `blueprints/p2/`
- Main user routes: `blueprints/p2/routes.py`
- Folder-specific routes and views: `blueprints/p2/folder_routes.py`
- Main folder UI: `blueprints/p2/templates/p2/folder_view_miospace.html`
- Product feature page: `blueprints/core/templates/core/features_p2.html`

## Main Entry Points

- Dashboard route: `dashboard()` in `blueprints/p2/routes.py`
- Login route: `login()` in `blueprints/p2/routes.py`
- Register route: `register()` in `blueprints/p2/routes.py`

## Related MioHub Features

- MioChat attachments can integrate with MioSpace folders.
- LaterGram saves clipped web content into the broader MioSpace hierarchy.
- Public profiles and public content views can expose selected MioSpace content externally.

## Recommended Reading

- Root project overview: `README.md`
- LaterGram product doc: `README_LATERGRAM.md`
- MioSpace feature page template: `blueprints/core/templates/core/features_p2.html`
