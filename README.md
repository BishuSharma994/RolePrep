# RolePrep

## Overview

RolePrep is an AI-powered interview system designed to simulate high-quality, adaptive interviews based on job descriptions (JD) and candidate resumes. The core interview engine is fully optimized and locked to ensure consistent evaluation quality.

---

## Core System (Locked)

The following components are finalized and must not be modified:

* JD parsing (core logic)
* Adaptive questioning
* Answer classification (contradiction / shallow / repetition / strong)
* Metric enforcement
* Trade-off enforcement
* Defensive challenge mechanism
* Scoring normalization
* Decision calibration
* Early termination logic

These ensure a 10/10 interview engine performance.

---

## New Feature Layer (Non-Intrusive)

All new features are implemented outside the conversation engine without altering:

* Question/answer flow
* Scoring logic

### 1. PDF Parsing Module

* Extracts text from resume and JD PDFs
* Built using PyMuPDF and pdfplumber
* Outputs structured data (role, requirements, skills)

Path:

```
backend/services/parser.py
```

---

### 2. Monetization Layer (Planned)

**Free Plan:**

* 1 session per day
* 5 questions per session

**Paid Plan:**

* Unlimited sessions
* Deep interview mode (10–15 questions)
* Detailed evaluation

---

### 3. Payment Integration (Planned)

* Razorpay / Stripe / Telegram payments
* Upgrade triggered after usage limit

---

### 4. User Dashboard (Planned)

* Interview history
* Score tracking
* Strength/weakness analysis

---

### 5. Multi-Round Interview Modes (Planned)

* HR Round
* Technical Round
* Leadership Round

Implemented via dynamic system prompts.

---

### 6. Resume vs JD Match Score (Planned)

* Pre-interview compatibility scoring
* Gap analysis

---

### 7. Voice Mode (Future)

* Speech-to-text input
* Same core engine

---

## Architecture

```
User (Telegram/Web)
        ↓
Bot Layer (unchanged)
        ↓
Interview Engine (locked)
        ↓
Additional Layers:
    - PDF Parser
    - Monetization System
    - Payment Gateway
    - Analytics/Dashboard
```

---

## Setup

### Install dependencies

```
pip install pymupdf pdfplumber
```

---

## Security

* `.env` is ignored and never committed
* API keys must be stored locally

---

## Status

* Core Interview Engine: Complete (Locked)
* PDF Parser: Implemented
* Monetization: Pending
* Payments: Pending
* Dashboard: Pending

---

## Goal

Convert a high-performance interview engine into a scalable, monetized product without altering core logic.
