# GlobalMedical Discussion Capture Extension

## Overview
This browser extension is a lightweight capture tool for discussion content from ChatGPT, Claude, GitHub, and similar pages.

Its purpose is to reduce manual copy/paste work and convert useful discussion into a format that fits the local AI workflow used in this repository.

This extension is designed to support:
- topic-based intake
- `inbox/<topic>/raw.md` or `discussion.md` preparation
- `./scripts/ai_pipeline.sh <topic>` workflow
- local-first handling of sensitive content

---

## Current Status
This is an early scaffold / prototype.

Implemented at scaffold level:
- Manifest V3 structure
- side panel UI
- selected text capture
- page text capture
- preview
- clipboard copy
- local extension storage save
- suggested pipeline command display

Not yet implemented:
- direct local file write to WSL/repository
- local bridge HTTP service
- advanced site-specific extraction
- GitHub API sync
- automatic pipeline execution

---

## Directory Structure
```text
browser_extension/
├── manifest.json
├── service_worker.js
├── content_script.js
├── sidepanel.html
├── sidepanel.js
├── styles.css
└── README.md