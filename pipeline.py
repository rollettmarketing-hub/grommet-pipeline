#!/usr/bin/env python3
"""
Grommet Lead Qualification Pipeline
Usage: python3 pipeline.py <brand_url>

Runs a brand URL through:
1. Shopify detection
2. Grommet First Look Filter (Tier 1/2/3 or Disqualified)
3. Contact email finder
4. Personalized outreach email saved as Gmail draft
"""

import sys
import os
import json
import base64
import re
from datetime import datetime
from email.mime.text import MIMEText

import anthropic

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials

try:
    import httpx
    def fetch_page(url):
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
        return response.text[:80000]
except ImportError:
    import urllib.request
    def fetch_page(url):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")[:80000]

# ── Config ────────────────────────────────────────────────────────────────────

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
SHEET_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "sheet_token.json")
ANTHROPIC_MODEL = "claude-opus-4-6"
SHEET_NAME = "Grommet Outreach Tracker"

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── Helper ────────────────────────────────────────────────────────────────────

def call_claude(prompt, max_tokens=1000):
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r'```json', '', raw)
    raw = re.sub(r'```', '', raw)
    return json.loads(raw.strip())

# ── Stage 1: Fetch page ───────────────────────────────────────────────────────

def get_page_html(url):
    print(f"\n🔍 Fetching: {url}")
    try:
        html = fetch_page(url)
        print(f"   ✓ Page fetched ({len(html):,} chars)")
        return html
    except Exception as e:
        print(f"   ✗ Failed to fetch page: {e}")
        sys.exit(1)

# ── Stage 2: Shopify detection ────────────────────────────────────────────────

def check_shopify(url, html):
    print("\n🛒 Checking Shopify...")

    prompt = f"""You are a platform detection tool. Analyze this webpage HTML and determine if it is built on Shopify.

Look for these Shopify fingerprints:
- cdn.shopify.com in any URLs
- myshopify.com anywhere in the source
- window.Shopify JavaScript object
- Shopify.theme references
- shopify-features script tags
- meta name="shopify-checkout-api-token"
- _shopify_ cookie names
- shopify-analytics references

URL: {url}

HTML:
{html}

Respond with ONLY a JSON object, no other text:
{{"is_shopify": true, "confidence": "HIGH", "signals_found": ["signal1", "signal2"], "platform_detected": "Shopify"}}"""

    try:
        result = call_claude(prompt, max_tokens=500)
    except Exception as e:
        print(f"   Could not parse Shopify response: {e}")
        sys.exit(1)

    if result.get("is_shopify"):
        print(f"   ✓ Shopify detected (confidence: {result.get('confidence')})")
        print(f"   Signals: {', '.join(result.get('signals_found', [])[:4])}")
    else:
        print(f"   ✗ Not on Shopify (platform: {result.get('platform_detected', 'Unknown')})")
        print("\n❌ DISQUALIFIED — Brand is not on Shopify.")
        sys.exit(0)

    return result

# ── Stage 3: First Look Filter ────────────────────────────────────────────────

def run_first_look_filter(url, html):
    print("\n🔎 Running First Look Filter...")

    prompt = f"""You are a product evaluator for Grommet, a product discovery marketplace.
Evaluate this product page using the Grommet First Look Filter.

URL: {url}
HTML: {html}

LANE A — Existential gates. If 2 or more fail = DISQUALIFIED. If Q1A and Q6 both fail = auto DISQUALIFIED.

Q1A: Clear Problem/Outcome — Does the page clearly state who it helps and how?
Q2: 15-Second Visual Demo — Could a silent video show problem, use, result?
Q5: Evidence It's Real — Live checkout, retailer reviews, crowdfunding, or customer proof?
Q6: Editorial Credibility — Real brand identity, founder story, social proof? FAIL if dropship/commodity patterns.
Q7: Commodity Risk — Meaningfully non-interchangeable? Patent, distinct design, origin story?

LANE B — Tier shaping only, does not disqualify:
Q3A: Category big enough for 7-figure potential?
Q3B: Broad audience appeal?
Q4: Price feels justified?
Q4B: Easy to understand what you are buying?

TIERS: Tier 1 = strong Lane B, broad appeal. Tier 2 = mixed, narrower. Tier 3 = charm/novelty, still credible.

Respond with ONLY this JSON, no other text:
{{"Q1A": true, "Q2": true, "Q5": true, "Q6": true, "Q7": true, "Q3A": true, "Q3B": true, "Q4": true, "Q4B": true, "lane_a_failures": [], "qualified": true, "tier": 1, "product_name": "name", "brand_name": "name", "one_sentence_take": "take", "disqualification_reason": null}}"""

    try:
        result = call_claude(prompt, max_tokens=1000)
    except Exception as e:
        print(f"   Could not parse First Look Filter response: {e}")
        sys.exit(1)

    print(f"   Product: {result.get('product_name')} by {result.get('brand_name')}")
    print(f"   Lane A — Q1A:{result['Q1A']} Q2:{result['Q2']} Q5:{result['Q5']} Q6:{result['Q6']} Q7:{result['Q7']}")

    if not result.get("qualified"):
        print(f"   ✗ Failed: {result.get('disqualification_reason')}")
        print("\n❌ DISQUALIFIED — Did not pass First Look Filter.")
        sys.exit(0)

    print(f"   ✓ QUALIFIED — Tier {result.get('tier')}")
    print(f"   Take: {result.get('one_sentence_take')}")

    return result

# ── Stage 4: Find & verify contact email ─────────────────────────────────────

HUNTER_API_KEY = "76b23fef752cc1eab397e37111556fd85ae30e72"
MIN_HUNTER_CONFIDENCE = 80  # Only use Hunter results at 80%+ confidence
EMAIL_SKIP_DOMAINS = ['shopify.com', 'example.com', 'sentry.io', 'w3.org',
                      'schema.org', 'cloudflare.com', 'google.com', 'apple.com']


def hunter_find(domain):
    """Use Hunter.io domain search to find the best email for a domain."""
    try:
        import urllib.request as urlreq
        import urllib.parse
        params = urllib.parse.urlencode({'domain': domain, 'api_key': HUNTER_API_KEY})
        req = urlreq.Request(f"https://api.hunter.io/v2/domain-search?{params}")
        with urlreq.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())

        emails = data.get('data', {}).get('emails', [])
        if not emails:
            return None, 0

        # Sort by confidence descending, prefer position types like CEO/founder
        priority_positions = ['ceo', 'founder', 'co-founder', 'owner', 'president',
                              'head', 'director', 'vp', 'marketing', 'growth']
        for email_data in sorted(emails, key=lambda x: x.get('confidence', 0), reverse=True):
            position = (email_data.get('position') or '').lower()
            confidence = email_data.get('confidence', 0)
            email = email_data.get('value', '')
            if confidence >= MIN_HUNTER_CONFIDENCE:
                # Prefer founder/exec emails
                if any(p in position for p in priority_positions):
                    return email, confidence
        # No priority match — return highest confidence if above threshold
        best = sorted(emails, key=lambda x: x.get('confidence', 0), reverse=True)[0]
        if best.get('confidence', 0) >= MIN_HUNTER_CONFIDENCE:
            return best.get('value', ''), best.get('confidence', 0)
    except Exception as e:
        print(f"   ⚠ Hunter find error: {e}")
    return None, 0


def hunter_verify(email):
    """Verify a specific email address via Hunter.io. Returns status and score."""
    try:
        import urllib.request as urlreq
        import urllib.parse
        params = urllib.parse.urlencode({'email': email, 'api_key': HUNTER_API_KEY})
        req = urlreq.Request(f"https://api.hunter.io/v2/email-verifier?{params}")
        with urlreq.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        status = data.get('data', {}).get('status', 'unknown')
        score = data.get('data', {}).get('score', 0)
        return status, score
    except Exception as e:
        print(f"   ⚠ Hunter verify error: {e}")
        return 'unknown', 0


def is_safe_to_send(email):
    """Run Hunter verification. Only return True if email is confirmed safe."""
    print(f"   🔍 Verifying: {email}")
    status, score = hunter_verify(email)
    print(f"   Verification: status={status}, score={score}")
    if status == 'valid' and score >= 70:
        return True
    if status in ['invalid', 'disposable', 'unknown']:
        print(f"   ✗ Dropped — status: {status}")
        return False
    if status == 'risky':
        print(f"   ✗ Dropped — too risky for cold outreach")
        return False
    return False


def scrape_emails_from_html(html):
    """Extract candidate emails from page HTML."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    found = re.findall(email_pattern, html)
    found = [e for e in found if not any(d in e for d in EMAIL_SKIP_DOMAINS)]
    priority_keywords = ['founder', 'hello', 'hi', 'contact', 'info', 'team', 'press', 'partner']
    priority = [e for e in found if any(k in e.lower() for k in priority_keywords)]
    return priority + [e for e in found if e not in priority]


def find_contact_email(url, html):
    """
    Four-layer email finder with deliverability protection:
    1. Hunter domain search (80%+ confidence only)
    2. Hunter verify the found email
    3. Scrape page HTML as fallback, verify scraped emails
    4. Leave blank if nothing passes verification
    """
    print("\n📧 Finding & verifying contact email...")

    domain = '/'.join(url.split('/')[:3]).replace('https://', '').replace('http://', '')
    domain = domain.split('/')[0]

    # Layer 1: Hunter domain search
    print(f"   Searching Hunter.io for: {domain}")
    hunter_email, confidence = hunter_find(domain)

    if hunter_email:
        print(f"   Hunter found: {hunter_email} (confidence: {confidence}%)")
        # Layer 2: Verify the Hunter result
        if is_safe_to_send(hunter_email):
            print(f"   ✓ Verified & safe: {hunter_email}")
            return hunter_email
        print(f"   ✗ Hunter email failed verification — trying page scrape")
    else:
        print(f"   Hunter: no result above {MIN_HUNTER_CONFIDENCE}% confidence")

    # Layer 3: Scrape page HTML
    candidates = scrape_emails_from_html(html)

    # Also try /pages/contact
    base_url = '/'.join(url.split('/')[:3])
    try:
        contact_html = fetch_page(f"{base_url}/pages/contact")
        candidates += scrape_emails_from_html(contact_html)
    except Exception:
        pass

    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for e in candidates:
        if e not in seen:
            seen.add(e)
            unique_candidates.append(e)

    for candidate in unique_candidates[:3]:  # Check up to 3 scraped candidates
        if is_safe_to_send(candidate):
            print(f"   ✓ Scraped & verified: {candidate}")
            return candidate

    # Layer 4: Nothing passed
    print("   — No verified email found. Leaving recipient blank.")
    return ""

# ── Stage 5: Find founder name ────────────────────────────────────────────────

def find_founder_name(html):
    prompt = f"""Look at this HTML and find the founder's first name ONLY if it is explicitly and obviously stated in an About section, founder quote, or signature. If not obvious, return null.

Respond with ONLY this JSON: {{"founder_name": "FirstName"}}
If not found: {{"founder_name": null}}

HTML: {html[:20000]}"""

    try:
        result = call_claude(prompt, max_tokens=100)
        name = result.get("founder_name")
        if name and str(name).lower() not in ["null", "none", ""]:
            return name
    except Exception:
        pass
    return None

# ── Stage 6: Draft outreach email ─────────────────────────────────────────────

def draft_email(url, html, filter_result):
    print("\n✉️  Drafting outreach email...")

    founder_name = find_founder_name(html)
    if founder_name:
        greeting = f"Hey {founder_name},"
        print(f"   Found founder name: {founder_name}")
    else:
        greeting = "Hey guys,"

    product_name = filter_result.get("product_name")
    brand_name = filter_result.get("brand_name")

    prompt = f"""Write a cold outreach email from Greg Rollett, Head of Growth at Grommet.

THIS IS THE EXACT EMAIL STRUCTURE AND TONE TO FOLLOW. DO NOT DEVIATE FROM THIS STRUCTURE:
---
Hey guys,

I spend most of my day hunting for products with that "it factor." Products that make millions of Grommet shoppers stop scrolling and pull out their credit card.

[THIS IS WHERE YOU PUT THE PERSONALIZED HOOK — 1-2 sentences about THIS specific brand/product using real details from their site. Include a specific customer review quote if there is a compelling one, or a specific product stat, feature, or story that makes this brand stand out. This paragraph must prove Greg actually spent time on their site.]

My name is Greg, Head of Growth at Grommet. Since 2008 we've helped 4,500+ products get discovered by 2.5M shoppers, including 120+ Shark Tank brands.

Here's what makes us different: zero upfront cost. You only pay after we generate a sale that goes straight to your Shopify store. Top performers get upgraded to our larger partner network (Bime Beauty did $550K in 60 days).

Can I send over a 2-minute Loom showing how it works?

Greg Rollett
Head of Growth, Grommet
---

BRAND DETAILS:
Brand: {brand_name}
Product: {product_name}
Greg's take: {filter_result.get("one_sentence_take")}

WEBSITE HTML — scan this for the personalized hook paragraph. Look for:
- Compelling customer review quotes
- Specific product stats or features
- FSA/HSA eligibility or insurance acceptance
- Number of users, countries, languages supported
- Awards, press mentions, or certifications
- Founder story or origin
- Anything that makes this brand genuinely stand out

{html[:40000]}

EXAMPLE OF A PERFECT HOOK PARAGRAPH (match this tone and style exactly):
"Smart glasses that display real-time captions for the deaf and hard of hearing, at $499 with FSA/HSA eligibility, is the kind of product that solves a problem most people didn't even know had a solution.

The fact that Captify Myvu is purpose-built for accessibility rather than being a tech gadget with captions bolted on gives it a distinct identity that's hard to ignore. That's exactly what stops our shoppers mid-scroll."

Notice what makes this great:
- It states what the product does and who it's for with specific details
- It explains WHY it's interesting without being generic
- It connects back to Grommet shoppers naturally
- It reads like enthusiasm, not a sales pitch or a product review
- It does NOT critique or give unsolicited advice to the brand
- The hook is split into two short paragraphs with a line break between them — never one long block

RULES:
- Use the EXACT structure above — do not reorder, add, or remove paragraphs
- The greeting is: {greeting}
- The sign off MUST be exactly: Greg Rollett\nHead of Growth, Grommet
- The personalized hook paragraph is the ONLY part that changes per brand
- Pull real specific details from their site — not generic observations
- NO buzzwords, NO corporate speak
- Do NOT start the hook with "I came across" or "I noticed" or "I recently"
- The hook describes what makes the product compelling — it does NOT critique, advise, or suggest improvements to the brand
- Write like a fan who discovered something cool, not a consultant giving feedback
- If there are customer reviews on the page, you CAN quote one briefly if it adds punch
- Never tell the brand what they should do differently on their website or marketing
- NEVER use em dashes (—) or hyphens used as dashes anywhere in the email body
- The hook paragraph MUST be split into two separate paragraphs with a blank line between them — never write it as one long block of text
- Use plain punctuation only: commas, periods, exclamation points, question marks

SUBJECT LINE FORMULA: "Can we put [Product Name] in front of 2M+ Shoppers?"
Use this exact formula with the actual product name.

Respond with ONLY this JSON, no other text:
{{"subject": "subject line", "body": "full email with greeting and sign off", "personalization_signals": ["specific detail from site 1", "specific detail 2", "specific detail 3"]}}"""

    try:
        result = call_claude(prompt, max_tokens=1000)
    except Exception as e:
        print(f"   Could not parse email draft: {e}")
        sys.exit(1)

    print(f"   ✓ Email drafted")
    print(f"   Subject: {result.get('subject')}")
    print(f"   Signals: {', '.join(result.get('personalization_signals', []))}")

    return result

# ── Stage 7: Save Gmail draft ─────────────────────────────────────────────────

def save_gmail_draft(email_data, recipient_email):
    print("\n📨 Saving Gmail draft...")

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)

    message = MIMEText(email_data["body"])
    message["subject"] = email_data["subject"]
    message["to"] = recipient_email

    raw_msg = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw_msg}}
    ).execute()

    print(f"   ✓ Draft saved (ID: {draft['id']})")
    if recipient_email:
        print(f"   Recipient pre-filled: {recipient_email}")
    else:
        print(f"   ⚠ No recipient found — add manually before sending")

    return draft["id"]


# ── Stage 8: Log to Google Sheets ────────────────────────────────────────────

def get_or_create_sheet():
    """Get existing tracker sheet or create it with headers."""
    creds = None
    if os.path.exists(SHEET_TOKEN_FILE):
        creds = OAuthCredentials.from_authorized_user_file(SHEET_TOKEN_FILE, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(SHEET_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    gc = gspread.authorize(creds)

    try:
        sheet = gc.open(SHEET_NAME).sheet1
    except gspread.SpreadsheetNotFound:
        # Create new sheet with headers
        spreadsheet = gc.create(SHEET_NAME)
        sheet = spreadsheet.sheet1
        headers = [
            "Date",
            "Brand Name",
            "Product Name",
            "URL",
            "Tier",
            "Email Subject",
            "Recipient Email",
            "One-Sentence Take",
            "Status",
            "Notes"
        ]
        sheet.append_row(headers)
        # Format header row bold
        sheet.format("A1:J1", {"textFormat": {"bold": True}})
        print(f"   ✓ Created new sheet: {SHEET_NAME}")

    return sheet


def log_to_sheet(url, filter_result, email_data, recipient_email):
    print("\n📊 Logging to Google Sheets...")
    try:
        sheet = get_or_create_sheet()
        row = [
            datetime.now().strftime("%Y-%m-%d"),
            filter_result.get("brand_name", ""),
            filter_result.get("product_name", ""),
            url,
            f"Tier {filter_result.get('tier', '')}",
            email_data.get("subject", ""),
            recipient_email,
            filter_result.get("one_sentence_take", ""),
            "Draft Created",
            ""
        ]
        sheet.append_row(row)
        print(f"   ✓ Logged: {filter_result.get('brand_name')} — {datetime.now().strftime('%Y-%m-%d')}")
    except Exception as e:
        print(f"   ⚠ Could not log to sheet: {e}")

# ── Stage 9: Summary ──────────────────────────────────────────────────────────

def print_summary(url, shopify_result, filter_result, email_data, recipient_email, draft_id):
    print("\n" + "="*60)
    print("✅ PIPELINE COMPLETE")
    print("="*60)
    print(f"URL:       {url}")
    print(f"Brand:     {filter_result.get('brand_name')}")
    print(f"Product:   {filter_result.get('product_name')}")
    print(f"Shopify:   YES ({shopify_result.get('confidence')} confidence)")
    print(f"Tier:      {filter_result.get('tier')}")
    print(f"Take:      {filter_result.get('one_sentence_take')}")
    print(f"Subject:   {email_data.get('subject')}")
    print(f"To:        {recipient_email if recipient_email else '⚠ Add manually'}")
    print(f"Draft ID:  {draft_id}")
    print("="*60)
    print("\n📋 Next steps:")
    print("  1. Open Gmail → Drafts")
    if not recipient_email:
        print("  2. ⚠ Add recipient email address")
    print("  3. Review, tweak if needed, and send!")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 pipeline.py <brand_url>")
        sys.exit(1)

    url = sys.argv[1]

    if not os.path.exists(CREDENTIALS_FILE):
        print("❌ credentials.json not found. Download from Google Cloud Console.")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    html = get_page_html(url)
    shopify_result = check_shopify(url, html)
    filter_result = run_first_look_filter(url, html)
    recipient_email = find_contact_email(url, html)
    email_data = draft_email(url, html, filter_result)
    draft_id = save_gmail_draft(email_data, recipient_email)
    log_to_sheet(url, filter_result, email_data, recipient_email)
    print_summary(url, shopify_result, filter_result, email_data, recipient_email, draft_id)

if __name__ == "__main__":
    main()
