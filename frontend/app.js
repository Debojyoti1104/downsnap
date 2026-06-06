/**
 * DownSnap – Frontend Application Logic
 * Multi-page architecture: index, downloader, facebook, instagram, youtube, pinterest, tiktok
 */

// ═══════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════
const _isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const API_BASE = _isLocal ? 'http://localhost:8000' : 'https://api.downsnap.in';

// ═══════════════════════════════════════════════════════
// PAGE CONTEXT
// ═══════════════════════════════════════════════════════
const PAGE_KEY = document.body.getAttribute('data-platform-key') || 'home';
const IS_PLATFORM_PAGE = document.body.getAttribute('data-platform') === 'true';

// ═══════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════
const state = {
  loading: false,
  results: null,
  theme: 'dark',
  // legacy tab support (index.html old-style, gracefully ignored on new pages)
  activeTab: PAGE_KEY === 'home' ? 'any' : PAGE_KEY,
};

// ═══════════════════════════════════════════════════════
// DOM REFERENCES  (null-safe — not all elements exist on every page)
// ═══════════════════════════════════════════════════════
const $ = (id) => document.getElementById(id);

const dom = {
  html:           document.documentElement,
  themeToggle:    $('theme-toggle'),
  iconSun:        $('icon-sun'),
  iconMoon:       $('icon-moon'),
  faqList:        $('faq-list'),

  // Results (shared by all pages)
  resultsSection: $('results-section'),
  resultsHeading: $('results-heading'),
  resultsCount:   $('results-count'),
  mediaFeed:      $('media-feed'),

  // Platform-page direct input (url-input-direct / fetch-btn-direct)
  urlInputDirect:     $('url-input-direct'),
  fetchBtnDirect:     $('fetch-btn-direct'),
  fetchIconDirect:    $('fetch-icon-direct'),
  fetchSpinnerDirect: $('fetch-spinner-direct'),
  fetchBtnTextDirect: $('fetch-btn-text-direct'),
  errorBoxDirect:     $('error-box-direct'),
  errorTextDirect:    $('error-text-direct'),

  // Home-page universal input (url-input / fetch-btn)
  urlInput:       $('url-input'),
  fetchBtn:       $('fetch-btn'),
  fetchIcon:      $('fetch-icon'),
  fetchSpinner:   $('fetch-spinner'),
  fetchBtnText:   $('fetch-btn-text'),
  errorBox:       $('error-box'),
  errorText:      $('error-text'),

  // Legacy tab support
  tabButtons:     document.querySelectorAll('.tab-btn'),
  subOptions:     $('sub-options-container'),
};

// ═══════════════════════════════════════════════════════
// INPUT / BUTTON HELPERS
// ═══════════════════════════════════════════════════════
function getActiveInput() {
  return IS_PLATFORM_PAGE ? dom.urlInputDirect : dom.urlInput;
}
function getActiveFetchBtn() {
  return IS_PLATFORM_PAGE ? dom.fetchBtnDirect : dom.fetchBtn;
}
function getActiveErrorBox() {
  return IS_PLATFORM_PAGE ? dom.errorBoxDirect : dom.errorBox;
}
function getActiveErrorText() {
  return IS_PLATFORM_PAGE ? dom.errorTextDirect : dom.errorText;
}
function getActiveIcon() {
  return IS_PLATFORM_PAGE ? dom.fetchIconDirect : dom.fetchIcon;
}
function getActiveSpinner() {
  return IS_PLATFORM_PAGE ? dom.fetchSpinnerDirect : dom.fetchSpinner;
}
function getActiveBtnText() {
  return IS_PLATFORM_PAGE ? dom.fetchBtnTextDirect : dom.fetchBtnText;
}

// ═══════════════════════════════════════════════════════
// PLATFORM SUB-OPTION BUTTONS (.pld-sub-btn)
// ═══════════════════════════════════════════════════════
function initPlatformSubOpts() {
  const subBtns = document.querySelectorAll('.pld-sub-btn');
  subBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      subBtns.forEach((b) => b.setAttribute('data-selected', 'false'));
      btn.setAttribute('data-selected', 'true');
      updateDirectInputPlaceholder();
    });
  });
}

function getSelectedPlatformSubOpt() {
  const sel = document.querySelector('.pld-sub-btn[data-selected="true"]');
  return sel ? sel.id : null;
}

function updateDirectInputPlaceholder() {
  const input = dom.urlInputDirect;
  if (!input) return;
  const sel = getSelectedPlatformSubOpt();
  const placeholders = {
    // Facebook
    'opt-fb-video': 'https://www.facebook.com/watch?v=… or fb.watch/…',
    'opt-fb-reel':  'https://www.facebook.com/reel/123456789',
    'opt-fb-story': 'https://www.facebook.com/stories/…',
    // Instagram
    'opt-ig-reel':  'https://www.instagram.com/reel/DCr8uByfeI/',
    'opt-ig-post':  'https://www.instagram.com/p/Cx7p8uByfeI/',
    'opt-ig-story': 'https://www.instagram.com/stories/username/…',
    // YouTube
    'opt-yt-video':  'https://www.youtube.com/watch?v=… or youtu.be/…',
    'opt-yt-shorts': 'https://www.youtube.com/shorts/…',
  };
  if (sel && placeholders[sel]) {
    input.placeholder = placeholders[sel];
  }
}

// ═══════════════════════════════════════════════════════
// LEGACY TABS (only used on old index.html if tab-bar exists)
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
      { id: 'opt-ig-post',  label: 'Post',  emoji: '🖼' },
      { id: 'opt-ig-reel',  label: 'Reel',  emoji: '🎥' },
    ],
  },
  any: {
    placeholderHint: 'Any public video URL — YouTube, Pinterest, TikTok, Instagram, Kuaishou…',
    subOptions: [],
    banner: 'Universal downloader for YouTube, Pinterest, Instagram, TikTok, Kuaishou & 1800+ sites. Powered by yt-dlp.',
  },
};

function switchTab(tabKey) {
  if (state.activeTab === tabKey) return;
  state.activeTab = tabKey;
  dom.tabButtons.forEach((btn) => {
    btn.setAttribute('aria-selected', String(btn.dataset.tab === tabKey));
  });
  if (dom.subOptions) renderSubOptions(tabKey);
  if (dom.urlInput) updateLegacyPlaceholder();
  clearResults();
}

function renderSubOptions(tabKey) {
  if (!dom.subOptions) return;
  const config = TAB_CONFIG[tabKey];
  dom.subOptions.innerHTML = '';
  if (!config) return;

  if (config.banner) {
    const banner = document.createElement('div');
    banner.className = 'platform-banner';
    banner.innerHTML = `<span class="platform-banner-icon" aria-hidden="true">🌐</span><span>${config.banner}</span>`;
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
  if (!dom.subOptions) return;
  dom.subOptions.querySelectorAll('.sub-opt-btn').forEach((btn) => {
    btn.dataset.selected = btn === clicked ? 'true' : 'false';
  });
  updateLegacyPlaceholder();
}

function getSelectedSubOption() {
  if (!dom.subOptions) return null;
  const sel = dom.subOptions.querySelector('.sub-opt-btn[data-selected="true"]');
  return sel ? sel.id : null;
}

function updateLegacyPlaceholder() {
  if (!dom.urlInput) return;
  const tab = TAB_CONFIG[state.activeTab];
  if (!tab || !tab.subOptions.length) return;
  const sel = getSelectedSubOption();
  if (!sel) return;
  const map = {
    'opt-ig-post': 'e.g. https://www.instagram.com/p/Cx7p8uByfeI/',
    'opt-ig-reel': 'e.g. https://www.instagram.com/reel/DCr8uByfeI/',
    'opt-fb-reel': 'e.g. https://www.facebook.com/reel/123456789',
    'opt-fb-video': 'e.g. https://www.facebook.com/watch?v=123456789',
  };
  if (map[sel]) dom.urlInput.placeholder = map[sel];
}

// ═══════════════════════════════════════════════════════
// VALIDATION
// ═══════════════════════════════════════════════════════
function validateUrl(rawUrl) {
  if (!rawUrl) return 'Please paste a URL first.';
  if (!rawUrl.match(/^https?:\/\//i) && !rawUrl.includes('.')) {
    return "That doesn't look like a valid URL. Make sure to include the full link.";
  }
  return null;
}

function validatePlatformUrl(rawUrl) {
  const sel = IS_PLATFORM_PAGE ? getSelectedPlatformSubOpt() : getSelectedSubOption();
  if (!sel) return null;
  const rules = {
    'opt-ig-post':  { re: /instagram\.com\/p\//i,      msg: "This doesn't look like an Instagram post. The URL should contain /p/ — e.g. instagram.com/p/XXXXXXX/" },
    'opt-ig-reel':  { re: /instagram\.com\/reel\//i,    msg: "This doesn't look like an Instagram Reel. The URL should contain /reel/ — e.g. instagram.com/reel/XXXXXXX/" },
    'opt-fb-reel':  { re: /(facebook\.com\/reel\/|fb\.watch\/)/i, msg: "This doesn't look like a Facebook Reel. The URL should contain /reel/ or be a fb.watch link." },
    'opt-fb-video': { re: /(facebook\.com\/(watch|video)|fb\.watch\/)/i, msg: "This doesn't look like a Facebook video. Use a facebook.com/watch?v= or fb.watch/ link." },
  };
  if (rules[sel] && !rules[sel].re.test(rawUrl)) return rules[sel].msg;
  return null;
}

// ═══════════════════════════════════════════════════════
// ERROR
// ═══════════════════════════════════════════════════════
function showError(msg) {
  const box = getActiveErrorBox();
  const txt = getActiveErrorText();
  if (box && txt) {
    txt.textContent = msg;
    box.classList.add('show');
  }
}

function clearError() {
  [dom.errorBox, dom.errorBoxDirect].forEach((box) => {
    if (box) box.classList.remove('show');
  });
  [dom.errorText, dom.errorTextDirect].forEach((txt) => {
    if (txt) txt.textContent = '';
  });
}

// ═══════════════════════════════════════════════════════
// LOADING
// ═══════════════════════════════════════════════════════
function setLoading(loading) {
  state.loading = loading;
  const btn     = getActiveFetchBtn();
  const icon    = getActiveIcon();
  const spinner = getActiveSpinner();
  const text    = getActiveBtnText();
  if (btn)     btn.disabled = loading;
  if (loading) {
    if (icon)    icon.classList.add('hidden');
    if (spinner) spinner.classList.remove('hidden');
    if (text)    text.textContent = 'Fetching…';
  } else {
    if (icon)    icon.classList.remove('hidden');
    if (spinner) spinner.classList.add('hidden');
    if (text)    text.textContent = 'Download Free';
  }
}

// ═══════════════════════════════════════════════════════
// RESULTS
// ═══════════════════════════════════════════════════════
function clearResults() {
  if (dom.resultsSection) dom.resultsSection.classList.remove('show');
  if (dom.mediaFeed)      dom.mediaFeed.innerHTML = '';
  if (dom.resultsHeading) dom.resultsHeading.textContent = '';
  if (dom.resultsCount)   dom.resultsCount.textContent = '';
}

function renderResults(data) {
  state.results = data;
  if (!dom.mediaFeed) return;
  dom.mediaFeed.innerHTML = '';

  const labels = { facebook: 'Facebook', instagram: 'Instagram', youtube: 'YouTube', generic: 'Web' };
  const label  = labels[data.platform] || 'Web';
  if (dom.resultsHeading) dom.resultsHeading.textContent = data.title ? truncate(data.title, 64) : `${label} Media`;
  if (dom.resultsCount)   dom.resultsCount.textContent   = `${data.media.length} item${data.media.length !== 1 ? 's' : ''}`;

  data.media.forEach((item, index) => {
    dom.mediaFeed.appendChild(buildMediaCard(item, index));
  });

  if (dom.resultsSection) {
    dom.resultsSection.classList.add('show');
    setTimeout(() => dom.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
  }
}

// ═══════════════════════════════════════════════════════
// MEDIA CARD
// ═══════════════════════════════════════════════════════
function buildMediaCard(item, index) {
  const isVideo = item.type === 'video';
  const card    = document.createElement('article');
  card.className = 'media-card';
  card.style.animationDelay = `${index * 60}ms`;
  card.setAttribute('aria-label', `${item.type} item ${index + 1}`);

  // Header
  const header   = document.createElement('div');
  header.className = 'media-card-header';
  const typeInfo = document.createElement('div');
  typeInfo.className = 'media-card-type';
  const badge    = document.createElement('span');
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

  // Preview
  const preview = document.createElement('div');
  preview.className = 'media-preview';
  if (isVideo) {
    const video    = document.createElement('video');
    video.controls = true;
    video.preload  = 'metadata';
    video.setAttribute('aria-label', `Video preview ${index + 1}`);
    if (item.thumbnail) video.poster = item.thumbnail;
    const source   = document.createElement('source');
    source.src     = buildProxyUrl(item.url);
    source.type    = 'video/mp4';
    video.appendChild(source);
    preview.appendChild(video);
  } else {
    const img    = document.createElement('img');
    img.src      = buildProxyUrl(item.url);
    img.alt      = item.title || `Photo ${index + 1}`;
    img.loading  = 'lazy';
    img.decoding = 'async';
    img.onerror  = () => { img.src = item.url; };
    preview.appendChild(img);
  }
  card.appendChild(preview);

  // Footer / Download
  const footer   = document.createElement('div');
  footer.className = 'media-card-footer';
  const dlBtn    = document.createElement('a');
  const ext      = isVideo ? '.mp4' : '.jpg';
  const fileName = `downsnap_${item.type}_${index + 1}${ext}`;
  dlBtn.id       = `dl-btn-${index}`;
  dlBtn.href     = buildProxyUrl(item.url, fileName);
  dlBtn.download = fileName;
  dlBtn.rel      = 'noopener noreferrer';
  dlBtn.className = `dl-btn${isVideo ? '' : ' photo-btn'}`;
  dlBtn.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
    <span>Download ${isVideo ? 'Video' : 'Photo'}</span>
  `;
  dlBtn.addEventListener('click', () => {
    const orig = dlBtn.innerHTML;
    dlBtn.innerHTML = `<span>Saving…</span>`;
    setTimeout(() => {
      dlBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Saved!</span>
      `;
      setTimeout(() => { dlBtn.innerHTML = orig; }, 2000);
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
  const params    = new URLSearchParams({ media_url: mediaUrl });
  if (filename)   params.set('filename', filename);
  const input     = getActiveInput();
  const sourceUrl = input ? input.value.trim() : '';
  if (sourceUrl)  params.set('source_url', sourceUrl);
  return `${API_BASE}/api/download-proxy?${params.toString()}`;
}

// ═══════════════════════════════════════════════════════
// FETCH / DOWNLOAD
// ═══════════════════════════════════════════════════════
async function handleFetch() {
  const input  = getActiveInput();
  const rawUrl = input ? input.value.trim() : '';

  clearError();
  clearResults();

  // Basic validation
  const basicErr = validateUrl(rawUrl);
  if (basicErr) { showError(basicErr); if (input) input.focus(); return; }

  // Platform-specific validation (sub-option match)
  const platformErr = validatePlatformUrl(rawUrl);
  if (platformErr) { showError(platformErr); return; }

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
          userMessage = d;
        } else if (Array.isArray(d)) {
          userMessage = d.map((e) => e.msg || JSON.stringify(e)).join('; ');
        } else if (d && typeof d === 'object') {
          userMessage = d.message || d.msg || JSON.stringify(d);
          if (d.hint) userMessage += ` — ${d.hint}`;
        }
      } catch (_) { /* keep default */ }

      const prefix = {
        403: '🔒 ', 404: '🔍 ', 410: '⚖️ ', 451: '🌍 ', 429: '⏳ ',
      }[response.status] || (response.status >= 500 ? '⚠️ ' : '❌ ');

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
// FAQ DATA — categorized by page context
// ═══════════════════════════════════════════════════════
const FAQ_ALL = [
  // Universal / global
  { tags: ['any','home'], q: 'How do I download any video from any website for free?', a: 'Copy the video URL from any website, paste it into DownSnap\'s input box, and click "Download Free". DownSnap supports 1800+ sites including YouTube, Instagram, TikTok, Facebook, Pinterest, Twitter/X, Reddit, Vimeo, and more. Your video will be ready in HD within seconds.' },
  { tags: ['any','home'], q: 'What websites does DownSnap support?', a: 'DownSnap is powered by yt-dlp and supports over 1,800 websites including YouTube, YouTube Shorts, Instagram, Facebook, TikTok, Pinterest, Twitter/X, Reddit, Vimeo, Dailymotion, Twitch, LinkedIn, SoundCloud, Kuaishou, Bilibili, Rumble and many more. Paste any public video URL and DownSnap will attempt to download it.' },
  { tags: ['any','home'], q: 'Is DownSnap free to use?', a: 'Yes. DownSnap is 100% free — no hidden costs, no subscriptions, no sign-up required, and no limits on how many videos you can download.' },
  { tags: ['any','home'], q: 'Does DownSnap add watermarks to downloaded videos?', a: 'No. DownSnap never adds watermarks. It streams the original source file directly from the platform\'s servers — no re-encoding, no compression, no overlays.' },
  { tags: ['any','home'], q: 'What video quality does DownSnap download?', a: 'DownSnap always selects the highest available quality — typically 720p or 1080p HD. For YouTube, 4K is available where the source provides it. No compression applied.' },
  { tags: ['any','home'], q: 'Is it safe to use DownSnap?', a: 'Yes. DownSnap never asks for your social media login credentials. It only fetches publicly accessible URLs. No files are stored on our servers — downloads are streamed directly to your device.' },
  { tags: ['any','home'], q: 'Does DownSnap work on iPhone and Android?', a: 'Yes. DownSnap is fully mobile-responsive. On iPhone/iOS, downloaded files are saved to your Files app or Photos library. On Android, they are saved to your Downloads folder. No app installation required.' },
  { tags: ['any','home'], q: 'Can I download TikTok videos without a watermark?', a: 'Yes. When downloading TikTok videos through DownSnap, the source video is fetched directly, which in many cases does not carry the TikTok watermark. Results depend on the TikTok API response at the time of download.' },
  { tags: ['any','home'], q: 'Can I download Reddit videos with audio?', a: 'Yes. DownSnap downloads Reddit videos with their audio track included, merged into a single MP4 file. This is a common issue with other tools that download video and audio separately.' },
  { tags: ['any','home'], q: 'Does DownSnap work without a browser extension?', a: 'Yes. DownSnap is a web-based tool that works entirely in your browser — no Chrome extension, Firefox add-on, or software installation needed. Just paste the URL and download.' },
  { tags: ['any','home'], q: 'Can I convert a video to MP3 with DownSnap?', a: 'DownSnap downloads the original video file (MP4). To extract audio, download the video then use a free converter like FFmpeg or an online MP3 converter. Some platforms like SoundCloud return audio files directly.' },
  { tags: ['any','home'], q: 'Can I download Kuaishou (快手) videos?', a: 'Yes. DownSnap supports Kuaishou video downloads. Copy the Kuaishou video link from the app or website, paste it into DownSnap, and click "Download Free". Your video will be ready in HD within seconds.' },

  // Facebook-specific
  { tags: ['facebook'], q: 'How do I download a Facebook video for free?', a: 'Go to the Facebook post, click the three-dot menu and choose "Copy link", or copy the URL from your browser. Paste it into DownSnap and click "Download Free". Your video will be ready in HD within seconds — no login or app required.' },
  { tags: ['facebook'], q: 'Can I download Facebook Reels without a watermark?', a: 'Yes. DownSnap downloads the original source file directly from Facebook\'s servers — no watermarks are added and no re-encoding is done. What you download is exactly what Facebook serves, in full HD.' },
  { tags: ['facebook'], q: 'How do I save a Facebook Story before it disappears?', a: 'Open the Facebook Story in your browser, copy the URL from the address bar, and paste it into DownSnap. Click "Download Free" and save the story video or photo to your device in HD instantly.' },
  { tags: ['facebook'], q: 'Does DownSnap work with fb.watch short links?', a: 'Yes. DownSnap supports both full facebook.com URLs and short fb.watch links. Simply paste either format and it will work correctly.' },
  { tags: ['facebook'], q: 'Can I download videos from Facebook groups or pages?', a: 'Yes. Any publicly accessible Facebook video — from personal profiles, groups, pages, or Facebook Watch — can be downloaded using DownSnap.' },
  { tags: ['facebook'], q: 'Does DownSnap require my Facebook login?', a: 'No. DownSnap never asks for your Facebook credentials. It only works with publicly accessible content. Private posts require authentication, which DownSnap does not support.' },

  // Instagram-specific
  { tags: ['instagram'], q: 'How do I download Instagram Reels without a watermark?', a: 'Open the Instagram Reel in your browser or tap Share and copy the link. Paste it into DownSnap and click "Download Free". The Reel is downloaded at full quality with no watermark added.' },
  { tags: ['instagram'], q: 'How do I download an entire Instagram carousel post?', a: 'Paste the Instagram post URL (e.g. instagram.com/p/XXXXXXX/) into DownSnap and click "Download Free". DownSnap extracts every image and video in the carousel as individual items — each with its own Download button.' },
  { tags: ['instagram'], q: 'Can I download Instagram Stories anonymously?', a: 'DownSnap downloads public Instagram Stories anonymously without notifying the account owner. It only works with public accounts — private stories are not accessible.' },
  { tags: ['instagram'], q: 'Can I download private Instagram posts?', a: 'No. DownSnap only works with publicly accessible content. Private accounts and posts require authentication which DownSnap does not support.' },
  { tags: ['instagram'], q: 'What types of Instagram content can I download?', a: 'DownSnap supports Instagram Reels, posts (photos and videos), carousel/multi-slide posts, IGTV videos, and public Stories. Each item gets its own download button.' },
  { tags: ['instagram'], q: 'Do I need an Instagram account to use DownSnap?', a: 'No. DownSnap works without any Instagram login. It only accesses publicly available content.' },

  // YouTube-specific
  { tags: ['youtube'], q: 'How do I download a YouTube video for free online?', a: 'Paste the YouTube video URL (e.g. youtube.com/watch?v=...) into DownSnap and click "Download Free". DownSnap will extract the highest available quality — typically 1080p HD — and let you download it directly to your device. No account, no app, completely free.' },
  { tags: ['youtube'], q: 'How do I download YouTube Shorts for free?', a: 'Open the YouTube Short in your browser. Copy the URL (it will contain /shorts/ in the address). Paste it into DownSnap and click "Download Free". The Short will be saved in full HD quality with no watermark.' },
  { tags: ['youtube'], q: 'What is the maximum quality DownSnap downloads from YouTube?', a: 'DownSnap downloads the best quality that includes both video and audio in a single file — typically 720p or 1080p. For some videos 4K may be available, subject to what the source provides.' },
  { tags: ['youtube'], q: 'Does DownSnap need a YouTube account to download videos?', a: 'No. DownSnap works without any YouTube account or Google login. It only supports publicly accessible YouTube videos — age-gated and private videos are not supported.' },
  { tags: ['youtube'], q: 'Can I download YouTube playlists with DownSnap?', a: 'DownSnap can process YouTube playlist URLs and will extract the available videos for download. Paste the playlist URL and click Download Free.' },
  { tags: ['youtube'], q: 'Does DownSnap work as a YouTube to MP4 converter?', a: 'Yes. DownSnap downloads YouTube videos as MP4 files — the most widely compatible video format. Simply paste the YouTube URL and click Download Free to get your MP4.' },

  // Pinterest-specific
  { tags: ['pinterest'], q: 'Can I download Pinterest videos?', a: 'Yes. DownSnap supports downloading Pinterest videos and video pins. Open the Pinterest video in your browser, copy the URL (e.g. pinterest.com/pin/…), paste it into DownSnap, and click "Download Free". The video will be saved in HD with no watermark.' },
  { tags: ['pinterest'], q: 'How do I save a Pinterest video to my phone?', a: 'Open the Pinterest video pin in your mobile browser, copy the URL from the address bar, and paste it into downsnap.in/pinterest.html. Tap "Download Free" — the video will save directly to your Camera Roll (iPhone) or Downloads folder (Android) without any app.' },
  { tags: ['pinterest'], q: 'Do I need a Pinterest account to download pins?', a: 'No. DownSnap downloads public Pinterest videos without requiring any Pinterest login or account.' },
  { tags: ['pinterest'], q: 'Can I download Pinterest idea pins?', a: 'DownSnap can download publicly accessible Pinterest video pins and idea pins that contain video content. Static image-only pins will download as images.' },

  // TikTok-specific
  { tags: ['tiktok'], q: 'How do I download TikTok videos without watermark?', a: 'Copy the TikTok video URL (from the app tap Share → Copy Link, or copy from your browser). Paste it into DownSnap and click Download Free. The video is fetched directly from TikTok\'s servers — in many cases without the TikTok watermark.' },
  { tags: ['tiktok'], q: 'Does DownSnap require a TikTok account?', a: 'No. DownSnap works without any TikTok login. It only works with publicly accessible TikTok videos — private accounts and videos require authentication which DownSnap does not support.' },
  { tags: ['tiktok'], q: 'Can I download TikTok videos on iPhone?', a: 'Yes. Open DownSnap in Safari on your iPhone, paste the TikTok URL, and tap Download Free. The video will save to your Photos or Files app. No TikTok app needed.' },
  { tags: ['tiktok'], q: 'Does DownSnap work with vm.tiktok.com short links?', a: 'Yes. DownSnap supports both full tiktok.com URLs and short vm.tiktok.com links. Just paste either format and click Download Free.' },
];

function getFaqForPage() {
  return FAQ_ALL.filter((f) => f.tags.includes(PAGE_KEY));
}

function renderFAQ() {
  if (!dom.faqList) return;
  const btns = dom.faqList.querySelectorAll('.faq-question');
  
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      const isOpen = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!isOpen));
      
      const ddId = btn.getAttribute('aria-controls');
      const dd = document.getElementById(ddId);
      if (dd) {
        dd.style.maxHeight = isOpen ? '0' : `${dd.scrollHeight}px`;
      }
    });
  });
}

// ═══════════════════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════════════════
function applyTheme(theme) {
  state.theme = theme;
  localStorage.setItem('downsnap-theme', theme);
  dom.html.setAttribute('data-theme', theme);
  if (dom.iconSun && dom.iconMoon) {
    if (theme === 'dark') {
      dom.iconSun.classList.remove('hidden');
      dom.iconMoon.classList.add('hidden');
    } else {
      dom.iconSun.classList.add('hidden');
      dom.iconMoon.classList.remove('hidden');
    }
  }
}

function initTheme() {
  const saved      = localStorage.getItem('downsnap-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(saved || (prefersDark ? 'dark' : 'light'));
}

if (dom.themeToggle) {
  dom.themeToggle.addEventListener('click', () => {
    applyTheme(state.theme === 'dark' ? 'light' : 'dark');
  });
}
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  if (!localStorage.getItem('downsnap-theme')) applyTheme(e.matches ? 'dark' : 'light');
});

// ═══════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════
function truncate(str, max) {
  return str.length > max ? str.slice(0, max) + '…' : str;
}
function formatDuration(secs) {
  const s   = Math.round(secs);
  const m   = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, '0')}`;
}

// ═══════════════════════════════════════════════════════
// EVENT BINDINGS
// ═══════════════════════════════════════════════════════

// Platform-page direct input
if (dom.fetchBtnDirect) {
  dom.fetchBtnDirect.addEventListener('click', () => {
    if (!state.loading) handleFetch();
  });
}
if (dom.urlInputDirect) {
  dom.urlInputDirect.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !state.loading) handleFetch();
  });
  dom.urlInputDirect.addEventListener('paste', () => {
    setTimeout(() => { if (dom.urlInputDirect.value.trim()) clearError(); }, 50);
  });
}

// Home-page / legacy input
if (dom.fetchBtn) {
  dom.fetchBtn.addEventListener('click', () => {
    if (!state.loading) handleFetch();
  });
}
if (dom.urlInput) {
  dom.urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !state.loading) handleFetch();
  });
  dom.urlInput.addEventListener('paste', () => {
    setTimeout(() => { if (dom.urlInput.value.trim()) clearError(); }, 50);
  });
}

// Legacy tabs
dom.tabButtons.forEach((btn) => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ═══════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════
(function init() {
  initTheme();

  // Legacy tabs init (index.html with tab-bar, ignored on new pages)
  if (dom.tabButtons.length > 0 && dom.subOptions) {
    const pageMap = {
      'youtube-downloader':      'any',
      'instagram-downloader':    'instagram',
      'online-video-downloader': 'any',
      'facebook-video-downloader': 'facebook',
      'pinterest-video-downloader': 'any',
    };
    const bodyPage  = document.body.getAttribute('data-page');
    const defaultTab = pageMap[bodyPage] || state.activeTab;
    switchTab(defaultTab);
  }

  // Platform sub-option buttons (new .pld-sub-btn style)
  initPlatformSubOpts();
  updateDirectInputPlaceholder();

  // FAQ
  renderFAQ();
})();

// ═══════════════════════════════════════════════════════
// 10. Legal Banner
// ═══════════════════════════════════════════════════════
function initLegalBanner() {
  if (localStorage.getItem('downsnap_terms_accepted') === 'true') {
    return; // Already accepted
  }
  
  const banner = document.createElement('div');
  banner.className = 'legal-banner';
  banner.innerHTML = `
    <p>
      By using DownSnap, you agree to our <a href="/terms.html">Terms of Service</a> and <a href="/privacy.html">Privacy Policy</a>. 
      You are solely responsible for ensuring you have the right to download and use the media. 
      Using this site constitutes full legal acceptance of these terms.
    </p>
    <button class="legal-banner-btn" id="legal-accept-btn">Accept All</button>
  `;
  
  document.body.appendChild(banner);
  
  // Animate in
  setTimeout(() => {
    banner.classList.add('show');
  }, 500);
  
  document.getElementById('legal-accept-btn').addEventListener('click', () => {
    localStorage.setItem('downsnap_terms_accepted', 'true');
    banner.classList.remove('show');
    setTimeout(() => {
      banner.remove();
    }, 400);
  });
}

// Call init on load
window.addEventListener('DOMContentLoaded', initLegalBanner);
