# AGENTS.md

## Project Overview
Global Medical Co., Ltd. repository.

This repository manages:
- Corporate website (GitHub Pages)
- Landing pages (enkakuka, kantei, karte)
- Business operation documents
- Issue-driven execution workflow

## Environment
- OS: Windows + WSL2 (Ubuntu)
- Path: ~/globalmedical/
- Deployment: GitHub Pages
- Workflow:
  1. edit
  2. git add .
  3. git commit
  4. git push ONLY when explicitly instructed

## Core Principles
- Minimize risk of unintended disclosure
- Maintain business credibility (medical/legal accuracy)
- Prefer small, controlled changes (minimal diff)
- Follow issue-driven workflow

## Strict Confidentiality Rules (CRITICAL)

DO NOT expose or describe in public materials:

### Remote system (遠隔化本舗)
- NIC exclusive assignment (L2 isolation specifics)
- USB-Ethernet device binding details
- .vmx configuration (e.g. usb.autoConnect)
- VMware KVM mode operation details
- Host/guest switching mechanism
- Any reproducible system-level implementation details

### KARTE
- Detailed system architecture
- AI pipeline design
- Internal data structure
- Any implementation enabling replication

### General
- Anything not yet filed in patent applications
- Anything marked as internal technical detail

## Business Rules

- 医療鑑定本舗:
  → DO NOT display pricing on website or FAXDM

- 投資家向け情報:
  → Technical details only after NDA

- 医療情報:
  → Must be accurate and defensable

## Design Rules

- Font:
  - Japanese: Noto Sans JP
  - English headings: Montserrat

- Style:
  - Mobile-first
  - Responsive (iPhone priority)

- Color themes:
  - Corporate: dark + blue/red
  - Kantei: dark + gold/red
  - KARTE: teal + warm tone

## Editing Policy

- Do NOT rewrite entire files unless necessary
- Preserve structure unless improvement is requested
- Prefer incremental improvements
- Keep tone consistent with existing site

## Output Requirements

When completing tasks:

1. List modified files
2. Describe changes clearly
3. Highlight any risk (especially disclosure)
4. DO NOT push without instruction

## If Uncertain

- If disclosure risk exists → ask before proceeding
- Otherwise → make minimal safe change
