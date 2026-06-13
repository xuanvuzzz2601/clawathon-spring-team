# Affiliate Media Generation & Referral Tracking System

A multi-agent system that automates product promotion through personalized media generation, affiliate link management, and referral reward tracking.

## System Overview

### Four Core Agents

**Agent 1: Product Reader & Media Generator**
- Reads product information from databases/APIs
- Generates multiple media formats (text posts, carousels, video scripts) via LLM — **VNG / ZaloPay / GreenNode content only** (competitor names blocked)
- Generates product images from text description using `gpt-image-1` — brand name enforced as `Zalopay` (lowercase p)
- A/B/C test variant generation with AI scoring
- **Post editor**: generated content renders as a social post preview — inline edit (title, body, hashtags, CTA), delete, and share to Facebook / Twitter / LinkedIn / Instagram / TikTok
- **Affiliate assignment**: admin can assign any post to an affiliate; affiliate users see only their own posts

**Agent 2: Media Personalization & Assembly**
- Customizes media based on individual affiliate profiles
- Adapts messaging by demographics (Gen Z, Millennial, Professional)
- A/B tests creative variations and selects best variant per audience
- Scores content relevance per affiliate

**Agent 3: Affiliate Link Generator**
- Generates unique tracking codes per referrer
- Commission tier multipliers: Bronze 1x → Silver 1.25x → Gold 1.5x → Platinum 2x
- Bulk link generation across all products
- Campaign attribution (default, summer_sale, new_user, loyalty, flash_sale)

**Agent 4: Referral Tracking & Rewards**
- Monitors click-through rates and conversions
- Calculates commission + performance bonuses
- AI-generated performance reports in Vietnamese
- Leaderboard ranking

---

## Authentication & Authorization

Two roles with role-based access control:

| Role | Access |
|------|--------|
| **Admin** | Full access: products CRUD, all affiliates, all analytics, pay rewards, simulate traffic |
| **Affiliate** | Own data only: their links, media, rewards; can generate content |

Default credentials:
- Admin: `admin` / `admin123`
- Affiliate accounts: `annguyen_fin`, `bichtran_style`, `duchminh_biz`, `hoablooms` — password `affiliate123`

---

## Tech Stack

### Backend
- **Runtime**: Python 3.10
- **Framework**: Flask 3.x + Flask-Login + Flask-SQLAlchemy
- **Database**: SQLite (via SQLAlchemy)
- **LLM (text)**: VNG Cloud MaaS — `google/gemma-4-31b-it`
- **LLM (images)**: OpenAI `gpt-image-1`

### Frontend
- **HTML5 + Tailwind CSS** (CDN)
- **Vanilla JavaScript** (SPA, tab-based)
- **Chart.js** for analytics charts
- **Role-aware UI**: tabs and actions shown/hidden by role

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Docker (for containerized deploy)
- OpenAI API key with `gpt-image-1` access (for image generation)

### Environment Variables

```env
# LLM for text content (VNG Cloud)
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
DEFAULT_LLM_MODEL=google/gemma-4-31b-it

# Image generation (real OpenAI)
IMAGE_API_KEY=sk-...
IMAGE_API_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
IMAGE_MODEL=openai/gpt-image-1

# App
APP_BASE_URL=http://localhost:8080
FLASK_SECRET_KEY=change-me-in-production
```

### Run locally

```bash
cd affiliate_system
pip install -r requirements.txt
python app.py
# → http://localhost:8080
```

### Run with Docker

```bash
cd affiliate_system
docker compose up -d
# → http://localhost:8080
```

---

## API Overview

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/login` | POST | Public | Login, returns session |
| `/api/auth/logout` | POST | Login | Logout |
| `/api/auth/me` | GET | Login | Current user info |
| `/api/dashboard` | GET | Login | Stats + leaderboard |
| `/api/products` | GET | Login | List products |
| `/api/products` | POST | Admin | Create product |
| `/api/affiliates` | GET/POST | Admin | Manage affiliates |
| `/api/links/generate` | POST | Login | Generate affiliate link |
| `/api/media/generate` | POST | Login | Generate text content (AI) |
| `/api/media/generate-image` | POST | Login | Generate image (gpt-image-1) |
| `/api/media/ab-test` | POST | Login | Generate 3 content variants |
| `/api/media/{id}` | PATCH | Login | Edit post (title, body, hashtags, CTA, affiliate) |
| `/api/media/{id}` | DELETE | Login | Delete a post |
| `/api/rewards/calculate` | POST | Login | Calculate commission |
| `/api/rewards/{id}/pay` | POST | Admin | Mark reward as paid |
| `/api/simulate-traffic` | POST | Admin | Demo traffic simulation |
| `/track/{code}` | GET | Public | Click tracking redirect |
| `/health` | GET | Public | Health check |
