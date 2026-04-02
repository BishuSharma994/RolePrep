# RolePrep

## Project Overview

RolePrep is a Telegram-based interview preparation platform built around controlled paid access to an interview engine. The system follows a production MVP model:

- user enters through Telegram
- payment creates entitlement
- entitlement controls access
- access controls protect the interview engine
- MongoDB Atlas persists all user, payment, webhook, and limiter state

The core operating model is:

- payment
- entitlement
- controlled access
- interview engine

## Current System Architecture

RolePrep is structured as:

- Telegram Bot
- Handler Layer
- Razorpay Payment Integration
- Razorpay Webhook Validation
- MongoDB Atlas Persistence
- Access Control and Rate Limiting
- Interview Engine

Primary backend flow:

- Telegram Bot receives user command or message
- Handler layer validates state and plan access
- Razorpay creates payment link when upgrade is required
- Webhook verifies signature and processes payment idempotently
- MongoDB Atlas stores payments, webhook events, users, audits, and rate limits
- Access control enforces session and question permissions
- Interview engine runs only after entitlement checks pass

The webhook path is designed to be idempotent and duplicate-safe using unique payment and event identifiers stored in MongoDB.

## Core Features Implemented

- Razorpay payment link integration
- Webhook signature verification
- MongoDB Atlas persistent storage
- Idempotent webhook processing
- Idempotent payment processing
- Audit logging for processed payments
- Structured event logging
- Entitlement system with strict plan priority:
  - premium
  - session
  - free
- Free plan:
  - 1 session per day
  - 5 questions per session
- Session credits:
  - ₹1 = 1 paid session
- Premium:
  - 28 days active duration
  - unlimited sessions
- Session limiter enforcement
- Question limiter enforcement
- Per-user request rate limiting
- Telegram `/status` visibility for credits and premium state

## System Capacity

The current system is suitable for production MVP usage with initial paid users.

- Stateless backend execution
- Restart-safe persistence
- Multi-user safe state handling
- MongoDB-backed concurrency handling
- Duplicate-safe payment and webhook operations
- Safe handling of concurrent webhook retries
- Suitable for early paid-user traffic at MVP scale

## Current Limitations

- No dedicated user dashboard outside Telegram
- No analytics or funnel reporting layer
- No alerting or external monitoring integration
- Limited admin tooling
- No documented automated backup workflow
- No horizontal scaling or worker queue layer yet

## Security & Reliability

- Razorpay webhook signature verification
- Unique payment ID enforcement
- Unique webhook event ID enforcement
- MongoDB as single source of truth
- No entitlement dependency on in-memory counters
- Per-user rate limiting
- Duplicate-safe payment crediting
- Duplicate-safe webhook handling
- Persistent audit trail for processed payments
- Deterministic access control priority:
  - premium > session > free

## Next Development Layers

### Layer 2 — User Visibility

- show credits, expiry, and current plan directly in bot UI
- introduce a basic user dashboard
- improve entitlement transparency after payments

### Layer 3 — Analytics

- usage tracking
- conversion tracking
- payment-to-activation metrics
- interview completion and success metrics

### Layer 4 — Monitoring & Alerts

- payment failure alerts
- webhook failure alerts
- database health monitoring
- bot availability monitoring

### Layer 5 — Backup & Recovery

- MongoDB backup policy
- restore procedure
- disaster recovery planning
- data retention policy

### Layer 6 — Scale & Infra

- horizontal scaling
- load balancing
- queue system for heavy workloads
- isolated worker execution for expensive tasks

## Final System State

RolePrep has evolved from a simple Telegram bot into a controlled entitlement platform.

The system now guarantees:

- payment correctness
- access correctness
- state persistence
- abuse protection

At its current stage, the backend is a production-oriented MVP with persistent state, deterministic entitlement logic, duplicate-safe payment processing, and request-level abuse controls.


# Test Sync new update new update new 