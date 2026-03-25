#!/usr/bin/env python3
"""
Grommet Pipeline Web UI
Run with: python3 app.py
Then open: http://localhost:5000
"""

import sys
import os

# Add parent directory to path so we can import pipeline functions
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template_string, request, Response, stream_with_context
import json
import queue
import threading

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grommet Pipeline</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f5f5f0;
            color: #1a1a1a;
            min-height: 100vh;
        }

        header {
            background: #1a1a1a;
            padding: 20px 40px;
            display: flex;
            align-items: center;
            gap: 16px;
        }

        header h1 {
            color: #fff;
            font-size: 20px;
            font-weight: 600;
            letter-spacing: -0.3px;
        }

        header span {
            color: #888;
            font-size: 14px;
        }

        .container {
            max-width: 760px;
            margin: 48px auto;
            padding: 0 24px;
        }

        .card {
            background: #fff;
            border-radius: 12px;
            padding: 32px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            margin-bottom: 24px;
        }

        .card h2 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #1a1a1a;
        }

        .input-row {
            display: flex;
            gap: 12px;
        }

        input[type="url"] {
            flex: 1;
            padding: 12px 16px;
            border: 1.5px solid #e0e0e0;
            border-radius: 8px;
            font-size: 15px;
            color: #1a1a1a;
            outline: none;
            transition: border-color 0.15s;
        }

        input[type="url"]:focus {
            border-color: #1a1a1a;
        }

        input[type="url"]::placeholder {
            color: #aaa;
        }

        button {
            padding: 12px 24px;
            background: #1a1a1a;
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            white-space: nowrap;
            transition: background 0.15s;
        }

        button:hover { background: #333; }
        button:disabled { background: #999; cursor: not-allowed; }

        /* Pipeline stages */
        .stages { display: flex; flex-direction: column; gap: 12px; }

        .stage {
            display: flex;
            align-items: flex-start;
            gap: 14px;
            padding: 14px 16px;
            border-radius: 8px;
            background: #f9f9f7;
            border: 1.5px solid #efefed;
            transition: all 0.2s;
        }

        .stage.running {
            background: #fffbeb;
            border-color: #fbbf24;
        }

        .stage.done {
            background: #f0fdf4;
            border-color: #86efac;
        }

        .stage.failed {
            background: #fef2f2;
            border-color: #fca5a5;
        }

        .stage.disqualified {
            background: #f8f8f8;
            border-color: #d1d5db;
        }

        .stage-icon {
            font-size: 20px;
            min-width: 28px;
            text-align: center;
            margin-top: 1px;
        }

        .stage-content { flex: 1; }

        .stage-title {
            font-size: 14px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 2px;
        }

        .stage-detail {
            font-size: 13px;
            color: #666;
            line-height: 1.5;
        }

        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #fbbf24;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.7s linear infinite;
            margin-right: 4px;
            vertical-align: middle;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Result card */
        .result-card {
            display: none;
        }

        .result-card.visible {
            display: block;
        }

        .result-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
        }

        .tier-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }

        .tier-1 { background: #d1fae5; color: #065f46; }
        .tier-2 { background: #dbeafe; color: #1e40af; }
        .tier-3 { background: #fef3c7; color: #92400e; }

        .email-preview {
            background: #f9f9f7;
            border: 1.5px solid #efefed;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .email-subject {
            font-size: 14px;
            font-weight: 600;
            color: #666;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .email-subject-line {
            font-size: 16px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 16px;
        }

        .email-body {
            font-size: 14px;
            color: #333;
            line-height: 1.7;
            white-space: pre-wrap;
        }

        .meta-row {
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }

        .meta-item {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .meta-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #999;
            font-weight: 600;
        }

        .meta-value {
            font-size: 14px;
            color: #1a1a1a;
            font-weight: 500;
        }

        .action-buttons {
            display: flex;
            gap: 12px;
        }

        .btn-secondary {
            background: #f0f0ee;
            color: #1a1a1a;
        }

        .btn-secondary:hover { background: #e0e0de; }

        .btn-override {
            margin-top: 14px;
            background: #fff;
            color: #b45309;
            border: 1.5px solid #b45309;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
        }
        .btn-override:hover { background: #fffbeb; }

        .disq-banner {
            display: none;
            padding: 16px 20px;
            background: #fff7ed;
            border: 1.5px solid #f59e0b;
            border-radius: 8px;
            font-size: 14px;
            color: #555;
            margin-top: 16px;
        }

        .disq-banner.visible { display: block; }

        footer {
            text-align: center;
            padding: 32px;
            color: #aaa;
            font-size: 13px;
        }
    </style>
</head>
<body>

<header>
    <h1>Grommet Pipeline</h1>
    <span>Lead Qualification + Outreach</span>
</header>

<div class="container">

    <!-- Input -->
    <div class="card">
        <h2>Run a Brand URL</h2>
        <div class="input-row">
            <input type="url" id="urlInput" placeholder="https://brand.com/products/product-name" />
            <button id="runBtn" onclick="runPipeline()">Run Pipeline</button>
        </div>
    </div>

    <!-- Pipeline stages -->
    <div class="card" id="stagesCard" style="display:none;">
        <h2>Pipeline Status</h2>
        <div class="stages">
            <div class="stage" id="stage-fetch">
                <div class="stage-icon">🔍</div>
                <div class="stage-content">
                    <div class="stage-title">Fetching Page</div>
                    <div class="stage-detail" id="detail-fetch">Waiting...</div>
                </div>
            </div>
            <div class="stage" id="stage-shopify">
                <div class="stage-icon">🛒</div>
                <div class="stage-content">
                    <div class="stage-title">Shopify Detection</div>
                    <div class="stage-detail" id="detail-shopify">Waiting...</div>
                </div>
            </div>
            <div class="stage" id="stage-filter">
                <div class="stage-icon">🔎</div>
                <div class="stage-content">
                    <div class="stage-title">First Look Filter</div>
                    <div class="stage-detail" id="detail-filter">Waiting...</div>
                </div>
            </div>
            <div class="stage" id="stage-email-find">
                <div class="stage-icon">📧</div>
                <div class="stage-content">
                    <div class="stage-title">Finding Contact Email</div>
                    <div class="stage-detail" id="detail-email-find">Waiting...</div>
                </div>
            </div>
            <div class="stage" id="stage-draft">
                <div class="stage-icon">✉️</div>
                <div class="stage-content">
                    <div class="stage-title">Drafting Email</div>
                    <div class="stage-detail" id="detail-draft">Waiting...</div>
                </div>
            </div>
            <div class="stage" id="stage-gmail">
                <div class="stage-icon">📨</div>
                <div class="stage-content">
                    <div class="stage-title">Saving Gmail Draft</div>
                    <div class="stage-detail" id="detail-gmail">Waiting...</div>
                </div>
            </div>
            <div class="stage" id="stage-sheet">
                <div class="stage-icon">📊</div>
                <div class="stage-content">
                    <div class="stage-title">Logging to Tracker</div>
                    <div class="stage-detail" id="detail-sheet">Waiting...</div>
                </div>
            </div>
        </div>
        <div class="disq-banner" id="disqBanner">
            <div id="disqReason"></div>
            <button class="btn-override" id="overrideBtn" onclick="overrideAndContinue()" style="display:none;">
                Override & Continue Anyway
            </button>
        </div>
    </div>

    <!-- Result -->
    <div class="card result-card" id="resultCard">
        <div class="result-header">
            <h2 id="resultBrand">Brand Name</h2>
            <span class="tier-badge" id="tierBadge">Tier 2</span>
        </div>

        <div class="meta-row">
            <div class="meta-item">
                <span class="meta-label">Product</span>
                <span class="meta-value" id="metaProduct">—</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">Recipient</span>
                <span class="meta-value" id="metaRecipient">—</span>
            </div>
        </div>

        <div class="email-preview">
            <div class="email-subject">Subject</div>
            <div class="email-subject-line" id="emailSubject">—</div>
            <div class="email-body" id="emailBody">—</div>
        </div>

        <div class="action-buttons">
            <button onclick="openGmail()">Open Gmail Drafts</button>
            <button class="btn-secondary" onclick="openSheet()">View Tracker Sheet</button>
            <button class="btn-secondary" onclick="resetUI()">Run Another</button>
        </div>
    </div>

</div>

<footer>Grommet Pipeline &mdash; Local</footer>

<script>
let sheetUrl = '';
let currentUrl = '';
let disqFilterData = null;

function setStage(id, state, detail) {
    const el = document.getElementById('stage-' + id);
    const detailEl = document.getElementById('detail-' + id);
    el.className = 'stage ' + state;
    if (detail) detailEl.innerHTML = detail;
}

function runPipeline() {
    const url = document.getElementById('urlInput').value.trim();
    if (!url) { alert('Please enter a brand URL'); return; }

    currentUrl = url;
    disqFilterData = null;
    document.getElementById('runBtn').disabled = true;
    document.getElementById('stagesCard').style.display = 'block';
    document.getElementById('resultCard').classList.remove('visible');
    document.getElementById('disqBanner').classList.remove('visible');

    // Reset all stages
    ['fetch','shopify','filter','email-find','draft','gmail','sheet'].forEach(s => {
        setStage(s, '', 'Waiting...');
    });

    const evtSource = new EventSource('/run?url=' + encodeURIComponent(url));

    evtSource.onmessage = function(e) {
        const data = JSON.parse(e.data);

        if (data.type === 'stage') {
            setStage(data.id, data.state, data.detail);
        }

        if (data.type === 'disqualified') {
            document.getElementById('disqReason').textContent = '❌ ' + data.reason;
            const showOverride = data.allow_override !== false;
            document.getElementById('overrideBtn').style.display = showOverride ? 'block' : 'none';
            if (data.filter_data) disqFilterData = data.filter_data;
            document.getElementById('disqBanner').classList.add('visible');
            document.getElementById('runBtn').disabled = false;
            evtSource.close();
        }

        if (data.type === 'complete') {
            sheetUrl = data.sheet_url || '';
            showResult(data);
            document.getElementById('runBtn').disabled = false;
            evtSource.close();
        }

        if (data.type === 'error') {
            alert('Pipeline error: ' + data.message);
            document.getElementById('runBtn').disabled = false;
            evtSource.close();
        }
    };

    evtSource.onerror = function() {
        document.getElementById('runBtn').disabled = false;
        evtSource.close();
    };
}

function showResult(data) {
    document.getElementById('resultCard').classList.add('visible');
    document.getElementById('resultBrand').textContent = data.brand_name;
    document.getElementById('metaProduct').textContent = data.product_name;
    document.getElementById('metaRecipient').textContent = data.recipient_email || '⚠ Add manually';
    document.getElementById('emailSubject').textContent = data.email_subject;
    document.getElementById('emailBody').textContent = data.email_body;

    const badge = document.getElementById('tierBadge');
    badge.textContent = 'Tier ' + data.tier;
    badge.className = 'tier-badge tier-' + data.tier;
}

function overrideAndContinue() {
    document.getElementById('overrideBtn').style.display = 'none';
    document.getElementById('disqReason').textContent += ' — Override applied, continuing...';
    document.getElementById('runBtn').disabled = true;

    const params = new URLSearchParams({ url: currentUrl, override: '1' });
    if (disqFilterData) params.append('filter_data', JSON.stringify(disqFilterData));

    const evtSource = new EventSource('/override?' + params.toString());

    evtSource.onmessage = function(e) {
        const data = JSON.parse(e.data);
        if (data.type === 'stage') setStage(data.id, data.state, data.detail);
        if (data.type === 'complete') {
            sheetUrl = data.sheet_url || '';
            showResult(data);
            document.getElementById('runBtn').disabled = false;
            evtSource.close();
        }
        if (data.type === 'error') {
            alert('Pipeline error: ' + data.message);
            document.getElementById('runBtn').disabled = false;
            evtSource.close();
        }
    };
    evtSource.onerror = function() {
        document.getElementById('runBtn').disabled = false;
        evtSource.close();
    };
}

function openGmail() {
    window.open('https://mail.google.com/mail/u/0/#drafts', '_blank');
}

function openSheet() {
    if (sheetUrl) {
        window.open(sheetUrl, '_blank');
    } else {
        window.open('https://drive.google.com', '_blank');
    }
}

function resetUI() {
    document.getElementById('urlInput').value = '';
    document.getElementById('stagesCard').style.display = 'none';
    document.getElementById('resultCard').classList.remove('visible');
    document.getElementById('disqBanner').classList.remove('visible');
    document.getElementById('disqReason').textContent = '';
    document.getElementById('overrideBtn').style.display = 'none';
    document.getElementById('runBtn').disabled = false;
    currentUrl = '';
    disqFilterData = null;
}

document.getElementById('urlInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') runPipeline();
});
</script>

</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/run')
def run():
    url = request.args.get('url', '').strip()
    if not url:
        return Response('data: {"type":"error","message":"No URL provided"}\n\n',
                        mimetype='text/event-stream')

    q = queue.Queue()

    def pipeline_thread():
        import re
        import json as pjson
        import base64
        import urllib.request
        import urllib.parse
        from datetime import datetime
        from email.mime.text import MIMEText

        import anthropic as ant
        import gspread
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        BASE_DIR = os.path.dirname(__file__)
        # Support cloud deployment via env vars — write creds to /tmp if provided
        if os.environ.get('GOOGLE_CREDENTIALS_JSON'):
            with open('/tmp/credentials.json', 'w') as _f:
                _f.write(os.environ['GOOGLE_CREDENTIALS_JSON'])
        if os.environ.get('GOOGLE_TOKEN_JSON'):
            with open('/tmp/token.json', 'w') as _f:
                _f.write(os.environ['GOOGLE_TOKEN_JSON'])
        CREDENTIALS_FILE = '/tmp/credentials.json' if os.environ.get('GOOGLE_CREDENTIALS_JSON') else os.path.join(BASE_DIR, 'credentials.json')
        TOKEN_FILE = '/tmp/token.json' if os.environ.get('GOOGLE_TOKEN_JSON') else os.path.join(BASE_DIR, 'token.json')
        SHEET_TOKEN_FILE = os.path.join(BASE_DIR, 'sheet_token.json')
        HUNTER_API_KEY = "76b23fef752cc1eab397e37111556fd85ae30e72"
        MIN_HUNTER_CONFIDENCE = 80
        EMAIL_SKIP_DOMAINS = ['shopify.com','example.com','sentry.io','w3.org',
                               'schema.org','cloudflare.com','google.com','apple.com']
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.compose',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file'
        ]
        SHEET_NAME = 'Grommet Outreach Tracker'
        MODEL = 'claude-opus-4-6'

        def emit(obj):
            q.put(obj)

        def call_claude(prompt, max_tokens=1000):
            client = ant.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=[{'role': 'user', 'content': prompt}]
            )
            raw = response.content[0].text.strip()
            raw = re.sub(r'```json', '', raw)
            raw = re.sub(r'```', '', raw)
            return pjson.loads(raw.strip())

        def fetch_page(u):
            try:
                import httpx
                r = httpx.get(u, headers={'User-Agent':'Mozilla/5.0'}, follow_redirects=True, timeout=15)
                return r.text[:80000]
            except Exception:
                req = urllib.request.Request(u, headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    return r.read().decode('utf-8', errors='ignore')[:80000]

        def get_creds():
            creds = None
            if os.path.exists(TOKEN_FILE):
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(TOKEN_FILE, 'w') as t:
                    t.write(creds.to_json())
            return creds

        try:
            # Stage 1: Fetch
            emit({'type':'stage','id':'fetch','state':'running','detail':'Fetching page...'})
            html = fetch_page(url)
            emit({'type':'stage','id':'fetch','state':'done','detail':f'Fetched {len(html):,} chars'})

            # Stage 2: Shopify
            emit({'type':'stage','id':'shopify','state':'running','detail':'Scanning for Shopify fingerprints...'})
            shopify_prompt = f"""Analyze this HTML and determine if the site is built on Shopify.
Look for: cdn.shopify.com, myshopify.com, window.Shopify, shopify-features, meta shopify-checkout-api-token.
URL: {url}
HTML: {html}
Respond with ONLY this JSON: {{"is_shopify": true, "confidence": "HIGH", "signals_found": ["s1","s2"], "platform_detected": "Shopify"}}"""
            shopify = call_claude(shopify_prompt, 500)
            if not shopify.get('is_shopify'):
                emit({'type':'stage','id':'shopify','state':'disqualified',
                      'detail':f"Not Shopify — platform: {shopify.get('platform_detected','Unknown')}"})
                emit({'type':'disqualified','reason':'Brand is not on Shopify.','allow_override':False})
                return
            emit({'type':'stage','id':'shopify','state':'done',
                  'detail':f"Shopify confirmed ({shopify.get('confidence')} confidence)"})

            # Stage 3: First Look Filter
            emit({'type':'stage','id':'filter','state':'running','detail':'Running First Look Filter...'})
            filter_prompt = f"""Evaluate this product page using the Grommet First Look Filter.
URL: {url}
HTML: {html}
LANE A gates (2+ failures = DISQUALIFIED, Q1A+Q6 both fail = auto DISQUALIFIED):
Q1A: Clear problem/outcome stated?
Q2: 15-second visual demo possible?
Q5: Evidence it's real (checkout, reviews, backers)?
Q6: Editorial credibility, real brand identity? FAIL if dropship/commodity.
Q7: Non-interchangeable? Patent, distinct design, origin story?
LANE B (tier shaping only):
Q3A: 7-figure category potential? Q3B: Broad appeal? Q4: Price justified? Q4B: Low friction?
TIERS: 1=strong broad appeal, 2=mixed narrower, 3=charm/novelty still credible.
Respond ONLY: {{"Q1A":true,"Q2":true,"Q5":true,"Q6":true,"Q7":true,"Q3A":true,"Q3B":true,"Q4":true,"Q4B":true,"lane_a_failures":[],"qualified":true,"tier":1,"product_name":"name","brand_name":"name","one_sentence_take":"take","disqualification_reason":null}}"""
            fltr = call_claude(filter_prompt, 1000)
            if not fltr.get('qualified'):
                emit({'type':'stage','id':'filter','state':'disqualified',
                      'detail':f"Failed: {fltr.get('disqualification_reason')}"})
                emit({'type':'disqualified',
                      'reason':f"Did not pass First Look Filter: {fltr.get('disqualification_reason')}",
                      'allow_override': True,
                      'filter_data': fltr})
                return
            emit({'type':'stage','id':'filter','state':'done',
                  'detail':f"{fltr.get('product_name')} by {fltr.get('brand_name')} — Tier {fltr.get('tier')}"})

            # Stage 4: Find email
            emit({'type':'stage','id':'email-find','state':'running','detail':'Searching Hunter.io...'})
            domain = url.replace('https://','').replace('http://','').split('/')[0]

            recipient_email = ''
            try:
                params = urllib.parse.urlencode({'domain':domain,'api_key':HUNTER_API_KEY})
                req = urllib.request.Request(f'https://api.hunter.io/v2/domain-search?{params}')
                with urllib.request.urlopen(req, timeout=10) as r:
                    hdata = pjson.loads(r.read().decode())
                emails = hdata.get('data',{}).get('emails',[])
                priority_pos = ['ceo','founder','co-founder','owner','head','director','vp','marketing','growth']
                best_email = None
                best_conf = 0
                for ed in sorted(emails, key=lambda x: x.get('confidence',0), reverse=True):
                    pos = (ed.get('position') or '').lower()
                    conf = ed.get('confidence',0)
                    if conf >= MIN_HUNTER_CONFIDENCE:
                        if any(p in pos for p in priority_pos):
                            best_email = ed.get('value','')
                            best_conf = conf
                            break
                if not best_email and emails:
                    top = sorted(emails, key=lambda x: x.get('confidence',0), reverse=True)[0]
                    if top.get('confidence',0) >= MIN_HUNTER_CONFIDENCE:
                        best_email = top.get('value','')
                        best_conf = top.get('confidence',0)

                if best_email:
                    # Verify it
                    vparams = urllib.parse.urlencode({'email':best_email,'api_key':HUNTER_API_KEY})
                    vreq = urllib.request.Request(f'https://api.hunter.io/v2/email-verifier?{vparams}')
                    with urllib.request.urlopen(vreq, timeout=10) as r:
                        vdata = pjson.loads(r.read().decode())
                    vstatus = vdata.get('data',{}).get('status','unknown')
                    vscore = vdata.get('data',{}).get('score',0)
                    if vstatus == 'valid' and vscore >= 70:
                        recipient_email = best_email
            except Exception as e:
                pass  # Fall through to scraping

            if not recipient_email:
                # Scrape multiple pages for email
                email_pat = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                base_url = '/'.join(url.split('/')[:3])
                contact_pages = [
                    base_url + '/pages/contact',
                    base_url + '/contact',
                    base_url + '/pages/contact-us',
                    base_url + '/contact-us',
                    base_url + '/pages/about',
                    base_url + '/about',
                ]
                all_html = html  # start with product page html
                for contact_url in contact_pages:
                    try:
                        extra_html = fetch_page(contact_url)
                        all_html += extra_html
                    except Exception:
                        continue

                candidates = [e for e in re.findall(email_pat, all_html)
                              if not any(d in e for d in EMAIL_SKIP_DOMAINS)]
                # Deduplicate while preserving order
                seen = set()
                unique_candidates = []
                for e in candidates:
                    if e not in seen:
                        seen.add(e)
                        unique_candidates.append(e)
                # Prioritize contact/hello/info style emails
                priority_kw = ['hello','hi','contact','info','team','press','partner','founder','support']
                priority = [e for e in unique_candidates if any(k in e.lower() for k in priority_kw)]
                ordered = priority + [e for e in unique_candidates if e not in priority]
                for c in ordered[:5]:
                    try:
                        vparams = urllib.parse.urlencode({'email':c,'api_key':HUNTER_API_KEY})
                        vreq = urllib.request.Request(f'https://api.hunter.io/v2/email-verifier?{vparams}')
                        with urllib.request.urlopen(vreq, timeout=10) as r:
                            vdata = pjson.loads(r.read().decode())
                        if vdata.get('data',{}).get('status') == 'valid':
                            recipient_email = c
                            break
                    except Exception:
                        continue

            if recipient_email:
                emit({'type':'stage','id':'email-find','state':'done',
                      'detail':f'Found & verified: {recipient_email}'})
            else:
                emit({'type':'stage','id':'email-find','state':'done',
                      'detail':'No verified email found — recipient left blank'})

            # Stage 5: Draft email
            emit({'type':'stage','id':'draft','state':'running','detail':'Drafting personalized email...'})

            # Find founder name
            fname_prompt = f"""Find founder first name ONLY if explicitly stated in About section or founder quote. Return ONLY: {{"founder_name": "Name or null"}}
HTML: {html[:20000]}"""
            try:
                fname_result = call_claude(fname_prompt, 100)
                fname = fname_result.get('founder_name')
                greeting = f"Hey {fname}," if fname and str(fname).lower() not in ['null','none',''] else "Hey guys,"
            except Exception:
                greeting = "Hey guys,"

            email_prompt = f"""Write a cold outreach email from Greg Rollett, Head of Growth at Grommet.

EXACT STRUCTURE TO FOLLOW — DO NOT DEVIATE:
---
Hey guys,

I spend most of my day hunting for products with that "it factor." Products that make millions of Grommet shoppers stop scrolling and pull out their credit card.

[PERSONALIZED HOOK — 2 paragraphs with a blank line between them. Specific details from their site only.]

My name is Greg, Head of Growth at Grommet. Since 2008 we've helped 4,500+ products get discovered by 2.5M shoppers, including 120+ Shark Tank brands.

Here's what makes us different: zero upfront cost. You only pay after we generate a sale that goes straight to your Shopify store. Top performers get upgraded to our larger partner network (Bime Beauty did $550K in 60 days).

Can I send over a 2-minute Loom showing how it works?

Greg Rollett
Head of Growth, Grommet
---

BRAND: {fltr.get('brand_name')} | PRODUCT: {fltr.get('product_name')} | TAKE: {fltr.get('one_sentence_take')}

HTML: {html[:40000]}

EXAMPLE PERFECT HOOK (this is the gold standard — match this energy exactly):
"A patented auto-locking earring back that fits, locks, and lifts any post earring is the kind of product that makes someone stop and think about every earring they've ever lost.

The fact that Chrysmela Catch works universally across any post earring and doubles as a lifter for drooping studs gives it real gifting range that goes way beyond a single use case. That's exactly what stops our shoppers mid-scroll."

Notice what makes this great:
- It leads with the INSIGHT about why a shopper would stop — not the product specs
- No price, no color options, no technical details the brand already knows
- Second paragraph explains the commercial angle — why it has range
- Ends by connecting back to Grommet shoppers

WHAT TO AVOID (bad examples — never do this):
- "priced at $55" — they know the price, leave it out
- "comes in Yellow Gold, Platinum, Rose Gold" — they know the colors
- Any product spec, SKU, dimension, or detail the brand already knows about their own product

RULES:
- Greeting: {greeting}
- Sign off: Greg Rollett\nHead of Growth, Grommet
- Hook MUST be exactly 2 paragraphs with a blank line between — never one block
- First hook paragraph: one sentence. The compelling observation about what the product does and why it matters to a shopper.
- Second hook paragraph: ONE sentence only. The angle or insight. End with something like "That's exactly what stops our shoppers mid-scroll." Do NOT add a third sentence explaining your reasoning.
- Write the INSIGHT — not WHAT the product does technically, and not WHY Greg thinks it works commercially
- The brand knows their product — write for a shopper discovering it for the first time
- No price, colors, dimensions, or product specs in the hook
- No meta-commentary ("this is why it works", "conversation starters drive impulse purchases") — state the insight and stop
- NEVER critique or advise the brand
- NEVER use em dashes (—)
- No buzzwords or corporate speak
- Subject formula: "Can we put [Product Name] in front of 2M+ Shoppers?"

Respond ONLY: {{"subject":"line","body":"full email","personalization_signals":["s1","s2","s3"]}}"""

            email_result = call_claude(email_prompt, 1000)
            emit({'type':'stage','id':'draft','state':'done',
                  'detail':f"Subject: {email_result.get('subject')}"})

            # Stage 6: Save Gmail draft
            emit({'type':'stage','id':'gmail','state':'running','detail':'Saving to Gmail drafts...'})
            creds = get_creds()
            service = build('gmail', 'v1', credentials=creds)
            msg = MIMEText(email_result['body'])
            msg['subject'] = email_result['subject']
            msg['to'] = recipient_email
            raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            draft = service.users().drafts().create(userId='me', body={'message':{'raw':raw_msg}}).execute()
            emit({'type':'stage','id':'gmail','state':'done','detail':f"Draft saved (ID: {draft['id']})"})

            # Stage 7: Log to sheet
            emit({'type':'stage','id':'sheet','state':'running','detail':'Logging to tracker...'})
            sheet_url = ''
            try:
                gc = gspread.authorize(creds)
                try:
                    spreadsheet = gc.open(SHEET_NAME)
                except gspread.SpreadsheetNotFound:
                    spreadsheet = gc.create(SHEET_NAME)
                    sheet = spreadsheet.sheet1
                    sheet.append_row(['Date','Brand Name','Product Name','URL','Tier',
                                      'Email Subject','Recipient Email','One-Sentence Take','Status','Notes'])
                    sheet.format('A1:J1', {'textFormat':{'bold':True}})
                sheet = spreadsheet.sheet1
                sheet.append_row([
                    datetime.now().strftime('%Y-%m-%d'),
                    fltr.get('brand_name',''),
                    fltr.get('product_name',''),
                    url,
                    f"Tier {fltr.get('tier','')}",
                    email_result.get('subject',''),
                    recipient_email,
                    fltr.get('one_sentence_take',''),
                    'Draft Created',
                    ''
                ])
                sheet_url = spreadsheet.url
                emit({'type':'stage','id':'sheet','state':'done',
                      'detail':f"Logged: {fltr.get('brand_name')} — {datetime.now().strftime('%Y-%m-%d')}"})
            except Exception as e:
                emit({'type':'stage','id':'sheet','state':'failed','detail':f'Sheet error: {e}'})

            emit({
                'type': 'complete',
                'brand_name': fltr.get('brand_name'),
                'product_name': fltr.get('product_name'),
                'tier': fltr.get('tier'),
                'recipient_email': recipient_email,
                'email_subject': email_result.get('subject'),
                'email_body': email_result.get('body'),
                'sheet_url': sheet_url
            })

        except Exception as e:
            emit({'type':'error','message':str(e)})

    thread = threading.Thread(target=pipeline_thread)
    thread.daemon = True
    thread.start()

    def generate():
        while True:
            try:
                item = q.get(timeout=120)
                yield f"data: {json.dumps(item)}\n\n"
                if item.get('type') in ('complete', 'disqualified', 'error'):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type':'error','message':'Pipeline timed out'})}\n\n"
                break

    return Response(stream_with_context(generate()), mimetype='text/event-stream')




@app.route('/override')
def override():
    url = request.args.get('url', '').strip()
    filter_data_raw = request.args.get('filter_data', '{}')
    if not url:
        return Response('data: {"type":"error","message":"No URL provided"}\n\n',
                        mimetype='text/event-stream')

    try:
        fltr = json.loads(filter_data_raw)
    except Exception:
        fltr = {}

    # If filter data is missing key fields, assign safe defaults
    if not fltr.get('brand_name'):
        fltr['brand_name'] = url.replace('https://','').replace('http://','').split('/')[0]
    if not fltr.get('product_name'):
        fltr['product_name'] = 'Product'
    if not fltr.get('tier'):
        fltr['tier'] = 2
    if not fltr.get('one_sentence_take'):
        fltr['one_sentence_take'] = 'Manually overridden — scout judgment applied.'

    q = queue.Queue()

    def override_thread():
        import re
        import json as pjson
        import base64
        import urllib.request
        import urllib.parse
        from datetime import datetime
        from email.mime.text import MIMEText

        import anthropic as ant
        import gspread
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        BASE_DIR = os.path.dirname(__file__)
        # Support cloud deployment via env vars — write creds to /tmp if provided
        if os.environ.get('GOOGLE_CREDENTIALS_JSON'):
            with open('/tmp/credentials.json', 'w') as _f:
                _f.write(os.environ['GOOGLE_CREDENTIALS_JSON'])
        if os.environ.get('GOOGLE_TOKEN_JSON'):
            with open('/tmp/token.json', 'w') as _f:
                _f.write(os.environ['GOOGLE_TOKEN_JSON'])
        CREDENTIALS_FILE = '/tmp/credentials.json' if os.environ.get('GOOGLE_CREDENTIALS_JSON') else os.path.join(BASE_DIR, 'credentials.json')
        TOKEN_FILE = '/tmp/token.json' if os.environ.get('GOOGLE_TOKEN_JSON') else os.path.join(BASE_DIR, 'token.json')
        HUNTER_API_KEY = "76b23fef752cc1eab397e37111556fd85ae30e72"
        MIN_HUNTER_CONFIDENCE = 80
        EMAIL_SKIP_DOMAINS = ['shopify.com','example.com','sentry.io','w3.org',
                               'schema.org','cloudflare.com','google.com','apple.com']
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.compose',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file'
        ]
        SHEET_NAME = 'Grommet Outreach Tracker'
        MODEL = 'claude-opus-4-6'

        def emit(obj):
            q.put(obj)

        def call_claude(prompt, max_tokens=1000):
            client = ant.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
            response = client.messages.create(
                model=MODEL, max_tokens=max_tokens,
                messages=[{'role': 'user', 'content': prompt}]
            )
            raw = response.content[0].text.strip()
            raw = re.sub(r'```json', '', raw)
            raw = re.sub(r'```', '', raw)
            return pjson.loads(raw.strip())

        def fetch_page(u):
            try:
                import httpx
                r = httpx.get(u, headers={'User-Agent':'Mozilla/5.0'}, follow_redirects=True, timeout=15)
                return r.text[:80000]
            except Exception:
                req = urllib.request.Request(u, headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as r:
                    return r.read().decode('utf-8', errors='ignore')[:80000]

        def get_creds():
            creds = None
            if os.path.exists(TOKEN_FILE):
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(TOKEN_FILE, 'w') as t:
                    t.write(creds.to_json())
            return creds

        try:
            # Re-fetch the page for email drafting
            emit({'type':'stage','id':'email-find','state':'running','detail':'Fetching page for email drafting...'})
            html = fetch_page(url)

            # Find contact email
            domain = url.replace('https://','').replace('http://','').split('/')[0]
            recipient_email = ''
            try:
                params = urllib.parse.urlencode({'domain':domain,'api_key':HUNTER_API_KEY})
                req = urllib.request.Request(f'https://api.hunter.io/v2/domain-search?{params}')
                with urllib.request.urlopen(req, timeout=10) as r:
                    hdata = pjson.loads(r.read().decode())
                emails = hdata.get('data',{}).get('emails',[])
                priority_pos = ['ceo','founder','co-founder','owner','head','director','vp','marketing','growth']
                best_email, best_conf = None, 0
                for ed in sorted(emails, key=lambda x: x.get('confidence',0), reverse=True):
                    pos = (ed.get('position') or '').lower()
                    conf = ed.get('confidence',0)
                    if conf >= MIN_HUNTER_CONFIDENCE:
                        if any(p in pos for p in priority_pos):
                            best_email, best_conf = ed.get('value',''), conf
                            break
                if not best_email and emails:
                    top = sorted(emails, key=lambda x: x.get('confidence',0), reverse=True)[0]
                    if top.get('confidence',0) >= MIN_HUNTER_CONFIDENCE:
                        best_email = top.get('value','')
                if best_email:
                    vparams = urllib.parse.urlencode({'email':best_email,'api_key':HUNTER_API_KEY})
                    vreq = urllib.request.Request(f'https://api.hunter.io/v2/email-verifier?{vparams}')
                    with urllib.request.urlopen(vreq, timeout=10) as r:
                        vdata = pjson.loads(r.read().decode())
                    if vdata.get('data',{}).get('status') == 'valid':
                        recipient_email = best_email
            except Exception:
                pass

            if not recipient_email:
                email_pat = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'
                candidates = [e for e in re.findall(email_pat, html)
                              if not any(d in e for d in EMAIL_SKIP_DOMAINS)]
                for c in candidates[:3]:
                    try:
                        vparams = urllib.parse.urlencode({'email':c,'api_key':HUNTER_API_KEY})
                        vreq = urllib.request.Request(f'https://api.hunter.io/v2/email-verifier?{vparams}')
                        with urllib.request.urlopen(vreq, timeout=10) as r:
                            vdata = pjson.loads(r.read().decode())
                        if vdata.get('data',{}).get('status') == 'valid':
                            recipient_email = c
                            break
                    except Exception:
                        continue

            emit({'type':'stage','id':'email-find','state':'done',
                  'detail': f'Found & verified: {recipient_email}' if recipient_email else 'No verified email found — recipient left blank'})

            # Draft email
            emit({'type':'stage','id':'draft','state':'running','detail':'Drafting personalized email...'})
            fname_prompt = f"""Find founder first name ONLY if explicitly stated in About section or founder quote. Return ONLY: {{"founder_name": "Name or null"}}
HTML: {html[:20000]}"""
            try:
                fname_result = call_claude(fname_prompt, 100)
                fname = fname_result.get('founder_name')
                greeting = f"Hey {fname}," if fname and str(fname).lower() not in ['null','none',''] else "Hey guys,"
            except Exception:
                greeting = "Hey guys,"

            email_prompt = f"""Write a cold outreach email from Greg Rollett, Head of Growth at Grommet.

EXACT STRUCTURE TO FOLLOW — DO NOT DEVIATE:
---
Hey guys,

I spend most of my day hunting for products with that "it factor." Products that make millions of Grommet shoppers stop scrolling and pull out their credit card.

[PERSONALIZED HOOK — 2 paragraphs with a blank line between them.]

My name is Greg, Head of Growth at Grommet. Since 2008 we've helped 4,500+ products get discovered by 2.5M shoppers, including 120+ Shark Tank brands.

Here's what makes us different: zero upfront cost. You only pay after we generate a sale that goes straight to your Shopify store. Top performers get upgraded to our larger partner network (Bime Beauty did $550K in 60 days).

Can I send over a 2-minute Loom showing how it works?

Greg Rollett
Head of Growth, Grommet
---

BRAND: {fltr.get('brand_name')} | PRODUCT: {fltr.get('product_name')} | TAKE: {fltr.get('one_sentence_take')}
HTML: {html[:40000]}

EXAMPLE PERFECT HOOK:
"A patented auto-locking earring back that fits, locks, and lifts any post earring is the kind of product that makes someone stop and think about every earring they've ever lost.

The fact that Chrysmela Catch works universally across any post earring and doubles as a lifter for drooping studs gives it real gifting range that goes way beyond a single use case. That's exactly what stops our shoppers mid-scroll."

RULES:
- Greeting: {greeting}
- Sign off: Greg Rollett\nHead of Growth, Grommet
- Hook MUST be 2 paragraphs with blank line between
- Write the INSIGHT about why it's interesting — not specs the brand already knows
- No price, colors, dimensions in the hook
- NEVER critique or advise the brand
- NEVER use em dashes
- Subject formula: "Can we put [Product Name] in front of 2M+ Shoppers?"

Respond ONLY: {{"subject":"line","body":"full email","personalization_signals":["s1","s2","s3"]}}"""

            email_result = call_claude(email_prompt, 1000)
            emit({'type':'stage','id':'draft','state':'done',
                  'detail':f"Subject: {email_result.get('subject')}"})

            # Save Gmail draft
            emit({'type':'stage','id':'gmail','state':'running','detail':'Saving to Gmail drafts...'})
            creds = get_creds()
            service = build('gmail', 'v1', credentials=creds)
            msg = MIMEText(email_result['body'])
            msg['subject'] = email_result['subject']
            msg['to'] = recipient_email
            raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            draft = service.users().drafts().create(userId='me', body={'message':{'raw':raw_msg}}).execute()
            emit({'type':'stage','id':'gmail','state':'done','detail':f"Draft saved (ID: {draft['id']})"})

            # Log to sheet with override status
            emit({'type':'stage','id':'sheet','state':'running','detail':'Logging to tracker...'})
            sheet_url = ''
            try:
                gc = gspread.authorize(creds)
                try:
                    spreadsheet = gc.open(SHEET_NAME)
                except gspread.SpreadsheetNotFound:
                    spreadsheet = gc.create(SHEET_NAME)
                    sheet = spreadsheet.sheet1
                    sheet.append_row(['Date','Brand Name','Product Name','URL','Tier',
                                      'Email Subject','Recipient Email','One-Sentence Take','Status','Notes'])
                    sheet.format('A1:J1', {'textFormat':{'bold':True}})
                sheet = spreadsheet.sheet1
                sheet.append_row([
                    datetime.now().strftime('%Y-%m-%d'),
                    fltr.get('brand_name',''),
                    fltr.get('product_name',''),
                    url,
                    f"Tier {fltr.get('tier','')} (Override)",
                    email_result.get('subject',''),
                    recipient_email,
                    fltr.get('one_sentence_take',''),
                    'Draft Created (Override)',
                    ''
                ])
                sheet_url = spreadsheet.url
                emit({'type':'stage','id':'sheet','state':'done',
                      'detail':f"Logged with override flag"})
            except Exception as e:
                emit({'type':'stage','id':'sheet','state':'failed','detail':f'Sheet error: {e}'})

            emit({
                'type': 'complete',
                'brand_name': fltr.get('brand_name'),
                'product_name': fltr.get('product_name'),
                'tier': fltr.get('tier', 2),
                'recipient_email': recipient_email,
                'email_subject': email_result.get('subject'),
                'email_body': email_result.get('body'),
                'sheet_url': sheet_url
            })

        except Exception as e:
            emit({'type':'error','message':str(e)})

    thread = threading.Thread(target=override_thread)
    thread.daemon = True
    thread.start()

    def generate():
        while True:
            try:
                item = q.get(timeout=120)
                yield f"data: {json.dumps(item)}\n\n"
                if item.get('type') in ('complete', 'error'):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type':'error','message':'Override timed out'})}\n\n"
                break

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    print("\n🚀 Grommet Pipeline UI starting...")
    print("   Open your browser to: http://127.0.0.1:5000\n")
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), threaded=True)
