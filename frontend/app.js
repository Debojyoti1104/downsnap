/**
 * DownSnap – Frontend Application Logic
 * Redesigned for vanilla CSS design system (no Tailwind)
 */

// ═══════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════
// Auto-detect API base:
//   • In production the FastAPI backend serves the frontend as static files,
//     so the API lives on the same origin — no hardcoded URL needed.
//   • In local dev (localhost / 127.0.0.1) fall back to port 8000.
const _isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const API_BASE = _isLocal ? 'http://localhost:8000' : window.location.origin;

// ═══════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════
const state = {
  activeTab: 'facebook',
  loading: false,
  results: null,
  theme: 'dark',
};

// ═══════════════════════════════════════════════════════
// DOM REFERENCES
// ═══════════════════════════════════════════════════════
const $ = (id) => document.getElementById(id);

const dom = {
  html:           document.documentElement,
  urlInput:       $('url-input'),
  fetchBtn:       $('fetch-btn'),
  fetchIcon:      $('fetch-icon'),
  fetchSpinner:   $('fetch-spinner'),
  fetchBtnText:   $('fetch-btn-text'),
  errorBox:       $('error-box'),
  errorText:      $('error-text'),
  subOptions:     $('sub-options-container'),
  resultsSection: $('results-section'),
  resultsHeading: $('results-heading'),
  resultsCount:   $('results-count'),
  mediaFeed:      $('media-feed'),
  tabButtons:     document.querySelectorAll('.tab-btn'),
  themeToggle:    $('theme-toggle'),
  iconSun:        $('icon-sun'),
  iconMoon:       $('icon-moon'),
  faqList:        $('faq-list'),
};

// ═══════════════════════════════════════════════════════
// TAB CONFIG
// ═══════════════════════════════════════════════════════
const TAB_CONFIG = {
  facebook: {
    placeholderHint: 'e.g. https://www.facebook.com/watch?v=… or fb.watch/…',
    subOptions: [
      { id: 'opt-fb-reel',  label: 'Reel',  emoji: '🎥' },
      { id: 'opt-fb-video', label: 'Video', emoji: '▶' },
    ],
  },
  instagram: {
    placeholderHint: 'e.g. https://www.instagram.com/p/… or /reel/…',
    subOptions: [
      { id: 'opt-ig-post',  label: 'Post',       emoji: '🖼' },
      { id: 'opt-ig-reel',  label: 'Reel',       emoji: '🎥' },
    ],
  },
  any: {
    placeholderHint: 'Any public video URL — YouTube, Pinterest, TikTok, Instagram, Kuaishou…',
    subOptions: [],
    banner: 'Universal downloader for YouTube, Pinterest, Instagram, TikTok, Kuaishou & 1800+ sites. Powered by yt-dlp.',
  },
};

// ═══════════════════════════════════════════════════════
// FAQ DATA
// ═══════════════════════════════════════════════════════
const FAQ_DATA = [
  // ── YouTube (§1 traffic source) ──
  {
    q: 'How do I download a YouTube video for free online?',
    a: 'Copy the YouTube video URL from your browser or the Share menu. Paste it into DownSnap and click “Download Free”. DownSnap extracts the highest available quality — typically 1080p HD — and downloads it directly to your device in seconds. No account, no app, completely free.',
  },
  {
    q: 'How do I download YouTube Shorts for free?',
    a: 'Open the YouTube Short in your browser. Copy the URL (it will contain /shorts/ in the address). Paste it into DownSnap and click “Download Free”. The Short will be saved to your device in full HD quality with no watermark.',
  },
  // ── Instagram (§2 traffic source) ──
  {
    q: 'How do I download Instagram Reels without a watermark?',
    a: 'Open the Instagram Reel in your browser or tap Share and copy the link. Paste it into DownSnap and click “Download Free”. The Reel is downloaded at full quality with no watermark added.',
  },
  {
    q: 'How do I download an entire Instagram carousel post?',
    a: 'Paste the Instagram post URL (e.g. instagram.com/p/XXXXXXX/) into DownSnap and click “Download Free”. DownSnap extracts every image and video in the carousel as individual downloadable items — each with its own Download button.',
  },
  {
    q: 'Can I download Instagram Stories without them knowing?',
    a: 'DownSnap downloads public Instagram stories anonymously without notifying the account owner. It only works with public accounts — private stories are not accessible.',
  },
  {
    q: 'Can I download private Instagram posts?',
    a: 'No. DownSnap only works with publicly accessible content. Private accounts and posts require account authentication, which DownSnap does not support in order to protect user privacy and security.',
  },
  // ── Pinterest (§3 traffic source, trending +6%) ──
  {
    q: 'Can I download Pinterest videos?',
    a: 'Yes. DownSnap supports downloading Pinterest videos and video pins. Open the Pinterest video in your browser, copy the URL (e.g. pinterest.com/pin/…), paste it into DownSnap, and click “Download Free”. The video will be saved in HD with no watermark.',
  },
  {
    q: 'How do I save a Pinterest video to my phone?',
    a: 'Open the Pinterest video pin in your mobile browser, copy the URL from the address bar, and paste it into downsnap.in. Tap “Download Free” — the video will save directly to your Camera Roll (iPhone) or Downloads folder (Android) without any app required.',
  },
  // ── Facebook ──
  {
    q: 'How do I download a Facebook video for free?',
    a: 'Go to the Facebook post, click the three-dot menu and choose “Copy link”, or copy the URL from your browser address bar. Paste it into DownSnap and click “Download Free”. Your video will be ready in HD within seconds — no login or app required.',
  },
  {
    q: 'Can I download Facebook Reels without a watermark?',
    a: 'Yes. DownSnap downloads the original source file directly from Facebook’s servers — no watermarks are added and no re-encoding is done. What you download is exactly what Facebook serves, in full HD.',
  },
  {
    q: 'How do I save a Facebook Story before it disappears?',
    a: 'Open the Facebook Story in your browser, copy the URL from the address bar, and paste it into DownSnap. Click “Download Free” and save the story video or photo to your device in HD instantly.',
  },
  {
    q: 'Does DownSnap work with fb.watch short links?',
    a: 'Yes. DownSnap supports both full facebook.com URLs and short fb.watch links. Simply paste either format and it will work correctly.',
  },
  // ── Trending platforms (Kuaishou +40%, Meta AI +30%) ──
  {
    q: 'Can I download Kuaishou (快手) videos?',
    a: 'Yes. DownSnap supports Kuaishou video downloads. Copy the Kuaishou video link from the app or website, paste it into DownSnap, and click “Download Free”. Your video will be ready in HD within seconds.',
  },
  {
    q: 'Can I convert a video to audio or MP3?',
    a: 'DownSnap downloads the original video file (MP4). To extract audio, paste the URL, download the video, then use a free converter like FFmpeg or an online MP3 converter to extract the audio track. Some platforms (like SoundCloud) return audio files directly.',
  },
  // ── Universal ──
  {
    q: 'What websites does DownSnap support?',
    a: 'DownSnap is powered by yt-dlp and supports over 1,800 websites including YouTube, YouTube Shorts, Instagram, Pinterest, TikTok, Twitter/X, Vimeo, Dailymotion, Reddit, Twitch, LinkedIn, SoundCloud, Kuaishou, Bilibili, Rumble and many more. Paste any public video URL and DownSnap will attempt to download it.',
  },
  {
    q: 'Can I download TikTok videos without a watermark?',
    a: 'Yes. When downloading TikTok videos through DownSnap, the source video is fetched directly, which in many cases does not carry the TikTok watermark. Results depend on the TikTok API response at the time of download.',
  },
  {
    q: 'Is DownSnap completely free?',
    a: 'Yes. DownSnap is 100% free — no hidden costs, no subscriptions, no sign-up required, and no limits on how many videos you can download.',
  },
  {
    q: 'Is it safe to use DownSnap?',
    a: 'Yes. DownSnap never asks for your social media login credentials. It only fetches publicly accessible URLs. No files are stored on our servers — downloads are streamed directly to your device.',
  },
  {
    q: 'Does DownSnap work on mobile (iPhone and Android)?',
    a: 'Yes. DownSnap is fully mobile-responsive. On iPhone/iOS, downloaded files are saved to your Files app or Photos library. On Android, they are saved to your Downloads folder.',
  },
  {
    q: 'What video quality does DownSnap download?',
    a: 'DownSnap always selects the highest available quality that includes both video and audio tracks — typically 720p or 1080p HD for most platforms. For YouTube, 4K is available where the source provides it.',
  },
];

// ═══════════════════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════════════════
function applyTheme(theme) {
  state.theme = theme;
  localStorage.setItem('downsnap-theme', theme);
  dom.html.setAttribute('data-theme', theme);

  if (theme === 'dark') {
    dom.iconSun.classList.remove('hidden');
    dom.iconMoon.classList.add('hidden');
  } else {
    dom.iconSun.classList.add('hidden');
    dom.iconMoon.classList.remove('hidden');
  }
}

function initTheme() {
  const saved = localStorage.getItem('downsnap-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(saved || (prefersDark ? 'dark' : 'light'));
}

dom.themeToggle.addEventListener('click', () => {
  applyTheme(state.theme === 'dark' ? 'light' : 'dark');
});

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  if (!localStorage.getItem('downsnap-theme')) {
    applyTheme(e.matches ? 'dark' : 'light');
  }
});

// ═══════════════════════════════════════════════════════
// TABS
// ═══════════════════════════════════════════════════════
function switchTab(tabKey) {
  if (state.activeTab === tabKey) return;
  state.activeTab = tabKey;

  dom.tabButtons.forEach((btn) => {
    const isActive = btn.dataset.tab === tabKey;
    btn.setAttribute('aria-selected', String(isActive));
  });

  renderSubOptions(tabKey);
  updatePlaceholder();
  clearResults();
}

function renderSubOptions(tabKey) {
  const config = TAB_CONFIG[tabKey];
  dom.subOptions.innerHTML = '';

  if (config.banner) {
    const banner = document.createElement('div');
    banner.className = 'platform-banner';
    banner.innerHTML = `
      <span class="platform-banner-icon" aria-hidden="true">🌐</span>
      <span>${config.banner}</span>
    `;
    dom.subOptions.appendChild(banner);
    return;
  }

  config.subOptions.forEach((opt, i) => {
    const btn = document.createElement('button');
    btn.id = opt.id;
    btn.type = 'button';
    btn.dataset.selected = i === 0 ? 'true' : 'false';
    btn.className = 'sub-opt-btn';
    btn.textContent = `${opt.emoji} ${opt.label}`;
    btn.addEventListener('click', () => selectSubOption(btn));
    dom.subOptions.appendChild(btn);
  });
}

function selectSubOption(clicked) {
  dom.subOptions.querySelectorAll('.sub-opt-btn').forEach((btn) => {
    btn.dataset.selected = btn === clicked ? 'true' : 'false';
  });
  updatePlaceholder();
}

function getSelectedSubOption() {
  const selected = dom.subOptions.querySelector('.sub-opt-btn[data-selected="true"]');
  return selected ? selected.id : null;
}

function updatePlaceholder() {
  const tab = TAB_CONFIG[state.activeTab];
  if (!tab || !tab.subOptions.length) return;
  const sel = getSelectedSubOption();
  if (!sel) return;
  if (state.activeTab === 'instagram') {
    if (sel === 'opt-ig-post') {
      dom.urlInput.placeholder = 'e.g. https://www.instagram.com/p/Cx7p8uByfeI/';
    } else if (sel === 'opt-ig-reel') {
      dom.urlInput.placeholder = 'e.g. https://www.instagram.com/reel/DCr8uByfeI/';
    }
  } else if (state.activeTab === 'facebook') {
    if (sel === 'opt-fb-reel') {
      dom.urlInput.placeholder = 'e.g. https://www.facebook.com/reel/123456789';
    } else if (sel === 'opt-fb-video') {
      dom.urlInput.placeholder = 'e.g. https://www.facebook.com/watch?v=123456789';
    }
  }
}

function validateInstagramUrl(url, subOption) {
  if (subOption === 'opt-ig-post' && !/instagram\.com\/p\//i.test(url)) {
    return 'This link doesn\'t appear to be an Instagram post. Make sure the URL contains /p/ — for example: https://www.instagram.com/p/Cx7p8uByfeI/';
  }
  if (subOption === 'opt-ig-reel' && !/instagram\.com\/reel\//i.test(url)) {
    return 'This link doesn\'t appear to be an Instagram Reel. Make sure the URL contains /reel/ — for example: https://www.instagram.com/reel/DCr8uByfeI/';
  }
  return null;
}

function validateFacebookUrl(url, subOption) {
  if (subOption === 'opt-fb-reel' && !/facebook\.com\/reel\//i.test(url) && !/fb\.watch\//i.test(url)) {
    return 'This link doesn\'t appear to be a Facebook Reel. Make sure the URL contains /reel/ — for example: https://www.facebook.com/reel/123456789';
  }
  if (subOption === 'opt-fb-video' && !/facebook\.com\/(watch|reel)/i.test(url) && !/fb\.watch\//i.test(url)) {
    return 'This link doesn\'t appear to be a Facebook video. Make sure the URL is a video link — for example: https://www.facebook.com/watch?v=123456789';
  }
  return null;
}

// ═══════════════════════════════════════════════════════
// ERROR
// ═══════════════════════════════════════════════════════
function showError(msg) {
  dom.errorText.textContent = msg;
  dom.errorBox.classList.add('show');
}

function clearError() {
  dom.errorBox.classList.remove('show');
  dom.errorText.textContent = '';
}

// ═══════════════════════════════════════════════════════
// LOADING
// ═══════════════════════════════════════════════════════
function setLoading(loading) {
  state.loading = loading;
  dom.fetchBtn.disabled = loading;

  if (loading) {
    dom.fetchIcon.classList.add('hidden');
    dom.fetchSpinner.classList.remove('hidden');
    dom.fetchBtnText.textContent = 'Fetching…';
  } else {
    dom.fetchIcon.classList.remove('hidden');
    dom.fetchSpinner.classList.add('hidden');
    dom.fetchBtnText.textContent = 'Download Free';
  }
}

// ═══════════════════════════════════════════════════════
// RESULTS
// ═══════════════════════════════════════════════════════
function clearResults() {
  dom.resultsSection.classList.remove('show');
  dom.mediaFeed.innerHTML = '';
  dom.resultsHeading.textContent = '';
  dom.resultsCount.textContent = '';
}

function renderResults(data) {
  state.results = data;
  dom.mediaFeed.innerHTML = '';

  const platformLabels = { facebook: 'Facebook', instagram: 'Instagram', youtube: 'YouTube', generic: 'Web' };
  const label = platformLabels[data.platform] || 'Web';
  dom.resultsHeading.textContent = data.title ? truncate(data.title, 64) : `${label} Media`;
  dom.resultsCount.textContent = `${data.media.length} item${data.media.length !== 1 ? 's' : ''}`;

  data.media.forEach((item, index) => {
    const card = buildMediaCard(item, index);
    dom.mediaFeed.appendChild(card);
  });

  dom.resultsSection.classList.add('show');
  setTimeout(() => dom.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
}

// ═══════════════════════════════════════════════════════
// MEDIA CARD
// ═══════════════════════════════════════════════════════
function buildMediaCard(item, index) {
  const isVideo = item.type === 'video';
  const card = document.createElement('article');
  card.className = 'media-card';
  card.style.animationDelay = `${index * 60}ms`;
  card.setAttribute('aria-label', `${item.type} item ${index + 1}`);

  // ── Header ──
  const header = document.createElement('div');
  header.className = 'media-card-header';

  const typeInfo = document.createElement('div');
  typeInfo.className = 'media-card-type';

  const badge = document.createElement('span');
  badge.className = `type-badge${isVideo ? '' : ' photo'}`;
  badge.setAttribute('aria-hidden', 'true');
  badge.innerHTML = isVideo
    ? `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`
    : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>`;

  typeInfo.appendChild(badge);
  typeInfo.appendChild(document.createTextNode(`${item.type} ${index + 1}`));

  header.appendChild(typeInfo);

  if (item.duration) {
    const dur = document.createElement('span');
    dur.className = 'media-card-duration';
    dur.textContent = formatDuration(item.duration);
    header.appendChild(dur);
  }

  card.appendChild(header);

  // ── Preview ──
  const preview = document.createElement('div');
  preview.className = 'media-preview';

  if (isVideo) {
    const video = document.createElement('video');
    video.controls = true;
    video.preload = 'metadata';
    video.setAttribute('aria-label', `Video preview ${index + 1}`);
    if (item.thumbnail) video.poster = item.thumbnail;

    const source = document.createElement('source');
    source.src = buildProxyUrl(item.url);
    source.type = 'video/mp4';
    video.appendChild(source);
    preview.appendChild(video);
  } else {
    const img = document.createElement('img');
    img.src = buildProxyUrl(item.url);
    img.alt = item.title || `Photo ${index + 1}`;
    img.loading = 'lazy';
    img.decoding = 'async';
    img.onerror = () => { img.src = item.url; };
    preview.appendChild(img);
  }

  card.appendChild(preview);

  // ── Footer / Download ──
  const footer = document.createElement('div');
  footer.className = 'media-card-footer';

  const dlBtn = document.createElement('a');
  const ext = isVideo ? '.mp4' : '.jpg';
  const fileName = `downsnap_${item.type}_${index + 1}${ext}`;
  dlBtn.id = `dl-btn-${index}`;
  dlBtn.href = buildProxyUrl(item.url, fileName);
  dlBtn.download = fileName;
  dlBtn.rel = 'noopener noreferrer';
  dlBtn.className = `dl-btn${isVideo ? '' : ' photo-btn'}`;
  dlBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
    <span>Download ${isVideo ? 'Video' : 'Photo'}</span>
  `;

  // Visual feedback on click
  dlBtn.addEventListener('click', () => {
    const originalHTML = dlBtn.innerHTML;
    dlBtn.innerHTML = `<span>Saving…</span>`;
    setTimeout(() => {
      dlBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Saved!</span>
      `;
      setTimeout(() => { dlBtn.innerHTML = originalHTML; }, 2000);
    }, 800);
  });

  footer.appendChild(dlBtn);
  card.appendChild(footer);

  return card;
}

// ═══════════════════════════════════════════════════════
// PROXY URL
// ═══════════════════════════════════════════════════════
function buildProxyUrl(mediaUrl, filename) {
  const params = new URLSearchParams({ media_url: mediaUrl });
  if (filename) params.set('filename', filename);
  const sourceUrl = dom.urlInput.value.trim();
  if (sourceUrl) params.set('source_url', sourceUrl);
  return `${API_BASE}/api/download-proxy?${params.toString()}`;
}

// ═══════════════════════════════════════════════════════
// FETCH
// ═══════════════════════════════════════════════════════
async function handleFetch() {
  const rawUrl = dom.urlInput.value.trim();

  clearError();
  clearResults();

  if (!rawUrl) {
    showError('Please paste a URL first.');
    dom.urlInput.focus();
    return;
  }

  if (!rawUrl.match(/^https?:\/\//i) && !rawUrl.includes('.')) {
    showError("That doesn't look like a valid URL. Make sure to include the full link.");
    return;
  }

  const subOption = getSelectedSubOption();
  if (state.activeTab === 'instagram' && subOption) {
    const igErr = validateInstagramUrl(rawUrl, subOption);
    if (igErr) { showError(igErr); return; }
  } else if (state.activeTab === 'facebook' && subOption) {
    const fbErr = validateFacebookUrl(rawUrl, subOption);
    if (fbErr) { showError(fbErr); return; }
  }

  setLoading(true);

  try {
    const response = await fetch(`${API_BASE}/api/fetch-info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: rawUrl }),
    });

    if (!response.ok) {
        let userMessage = 'An unknown error occurred. Please try again.';
        try {
          const errData = await response.json();
          const d = errData.detail;
          if (typeof d === 'string') {
            // Plain string detail (e.g. from download-proxy or simple raises)
            userMessage = d;
          } else if (Array.isArray(d)) {
            // Pydantic v2 validation error array: [{loc, msg, type}]
            userMessage = d.map(e => e.msg || JSON.stringify(e)).join('; ');
          } else if (d && typeof d === 'object') {
            // Our structured errors: {code, message, hint}
            userMessage = d.message || d.msg || JSON.stringify(d);
            if (d.hint) userMessage += ` — ${d.hint}`;
          }
        } catch (e) { /* keep default */ }

        let prefix = '❌ ';
        if (response.status === 403)  prefix = '🔒 ';
        else if (response.status === 404) prefix = '🔍 ';
        else if (response.status === 410) prefix = '⚖️ ';
        else if (response.status === 451) prefix = '🌍 ';
        else if (response.status === 429) prefix = '⏳ ';
        else if (response.status >= 500) prefix = '⚠️ ';

        showError(prefix + userMessage);
        return;
      }

    const data = await response.json();

    if (!data.media || data.media.length === 0) {
      showError('No media items were found in this post.');
      return;
    }

    renderResults(data);

  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      showError('🔌 Cannot connect to DownSnap server. Make sure the backend is running on port 8000.');
    } else {
      showError(`Unexpected error: ${err.message}`);
    }
    console.error('[DownSnap] Fetch error:', err);
  } finally {
    setLoading(false);
  }
}

// ═══════════════════════════════════════════════════════
// FAQ ACCORDION
// ═══════════════════════════════════════════════════════
function renderFAQ() {
  FAQ_DATA.forEach((faq, i) => {
    const item = document.createElement('div');
    item.className = 'faq-item';

    const qId = `faq-q-${i}`;
    const aId = `faq-a-${i}`;

    const dt = document.createElement('dt');
    const btn = document.createElement('button');
    btn.id = qId;
    btn.type = 'button';
    btn.className = 'faq-question';
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', aId);
    btn.innerHTML = `
      <span>${faq.q}</span>
      <svg class="faq-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
      </svg>
    `;
    dt.appendChild(btn);

    const dd = document.createElement('dd');
    dd.id = aId;
    dd.className = 'faq-answer';
    dd.setAttribute('role', 'region');
    dd.setAttribute('aria-labelledby', qId);
    dd.innerHTML = `<p>${faq.a}</p>`;

    btn.addEventListener('click', () => {
      const isOpen = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!isOpen));
      dd.style.maxHeight = isOpen ? '0' : `${dd.scrollHeight}px`;
    });

    item.appendChild(dt);
    item.appendChild(dd);
    dom.faqList.appendChild(item);
  });
}

// ═══════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════
function truncate(str, max) {
  return str.length > max ? str.slice(0, max) + '…' : str;
}

function formatDuration(secs) {
  const s = Math.round(secs);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

// ═══════════════════════════════════════════════════════
// EVENT BINDINGS
// ═══════════════════════════════════════════════════════
dom.fetchBtn.addEventListener('click', () => {
  if (!state.loading) handleFetch();
});

dom.urlInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !state.loading) handleFetch();
});

dom.urlInput.addEventListener('paste', () => {
  setTimeout(() => {
    if (dom.urlInput.value.trim()) clearError();
  }, 50);
});

dom.tabButtons.forEach((btn) => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ═══════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════
(function init() {
  initTheme();
  switchTab('facebook');
  renderFAQ();
})();
