// Cloudflare Worker 版 OneJav 图片优先 RSS 订阅
// 原理: 每次被访问时实时抓取 onejav.com/new, 现场生成 RSS 2.0 + Media RSS,
//       订阅地址即 Worker 的 URL, 无需 GitHub、无需数据库。
// 部署见同目录 README.md

const LIST_URL = 'https://onejav.com/new';
const SITE = 'https://onejav.com';
const UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';

const MONTHS = {
  jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
  jul: 7, aug: 8, sep: 9, sept: 9, oct: 10, nov: 11, dec: 12,
};

function parseDate(s) {
  const m = /([A-Za-z]+)\.\s*(\d{1,2}),\s*(\d{4})/.exec(s || '');
  if (!m) return '';
  const mon = MONTHS[m[1].toLowerCase()];
  if (!mon) return '';
  return `${m[3]}-${String(mon).padStart(2, '0')}-${String(+m[2]).padStart(2, '0')}`;
}

function esc(s) {
  return (s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function mime(url) {
  const u = (url || '').toLowerCase().split('?')[0];
  if (u.endsWith('.png')) return 'image/png';
  if (u.endsWith('.gif')) return 'image/gif';
  if (u.endsWith('.webp')) return 'image/webp';
  return 'image/jpeg';
}

async function fetchListHtml() {
  let lastErr = null;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const res = await fetch(LIST_URL, {
        headers: { 'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9' },
      });
      if (!res.ok) throw new Error(`onejav.com 返回 ${res.status}`);
      return await res.text();
    } catch (e) {
      lastErr = e;
      if (attempt < 3) await new Promise((r) => setTimeout(r, 5000 * attempt));
    }
  }
  throw lastErr;
}

// 用 Cloudflare 原生的 HTMLRewriter 按卡片结构提取条目
async function fetchItems() {
  const html = await fetchListHtml();
  const items = [];
  let cur = null;
  const push = () => { if (cur && cur.url) items.push(cur); cur = null; };

  const rw = new HTMLRewriter()
    .on('div.card.mb-3', {
      element() { push(); cur = { code: '', title: '', url: '', image: '', date: '' }; },
    })
    .on('div.card.mb-3 h5.title.is-4.is-spaced a', {
      element(el) {
        const m = /\/torrent\/([a-z0-9]+)/.exec(el.getAttribute('href') || '');
        if (m && cur) cur.url = `${SITE}/torrent/${m[1]}`;
      },
      text(t) { if (cur) cur.code += t.text; },
    })
    .on('div.card.mb-3 img.image', {
      element(el) {
        if (!cur) return;
        const s = el.getAttribute('src') || '';
        cur.image = s.startsWith('data:') ? '' : s;
      },
    })
    .on('div.card.mb-3 p.subtitle.is-6 a', {
      text(t) { if (cur) cur.dateRaw = (cur.dateRaw || '') + t.text; },
    })
    .on('div.card.mb-3 p.level.has-text-grey-dark', {
      text(t) { if (cur) cur.title += t.text; },
    });

  await rw.transform(new Response(html)).text(); // 驱动解析
  push();
  for (const it of items) {
    it.code = it.code.trim();
    it.title = it.title.trim();
    it.date = parseDate(it.dateRaw || '');
    delete it.dateRaw;
  }
  return items;
}

function buildRSS(items) {
  const now = new Date().toUTCString();
  const body = items.map((it) => {
    const title =
      it.code && it.title
        ? `【${esc(it.code)}】${esc(it.title)}`
        : esc(it.code || it.title);
    const img = it.image
      ? `<p style="margin:0 0 12px 0;text-align:center;"><a href="${esc(it.url)}">` +
        `<img src="${esc(it.image)}" style="max-width:100%;height:auto;border-radius:8px;" ` +
        `alt="${esc(it.code)}"/></a></p>`
      : '';
    const meta = it.date ? `<p>日期: ${esc(it.date)}</p>` : '';
    const media = it.image
      ? `      <media:thumbnail url="${esc(it.image)}"/>\n` +
        `      <media:content url="${esc(it.image)}" type="${mime(it.image)}" medium="image"/>\n` +
        `      <enclosure url="${esc(it.image)}" type="${mime(it.image)}"/>\n`
      : '';
    const pubDate = it.date
      ? `      <pubDate>${new Date(it.date + 'T00:00:00Z').toUTCString()}</pubDate>\n`
      : '';
    return `    <item>\n` +
      `      <title>${title}</title>\n` +
      `      <link>${esc(it.url)}</link>\n` +
      `      <guid isPermaLink="true">${esc(it.url)}</guid>\n` +
      pubDate + media +
      `      <description><![CDATA[${img}${meta}${it.title ? `<p>${esc(it.title)}</p>` : ''}]]></description>\n` +
      `    </item>`;
  }).join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>\n` +
`<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">\n` +
`  <channel>\n` +
`    <title>OneJav 每日更新</title>\n` +
`    <link>${SITE}/new</link>\n` +
`    <description>OneJav 每日新片速递 — 封面图优先展示</description>\n` +
`    <language>zh-cn</language>\n` +
`    <lastBuildDate>${now}</lastBuildDate>\n` +
`    <!-- 共 ${items.length} 条, Cloudflare Worker 实时生成 -->\n` +
body + `\n  </channel>\n</rss>\n`;
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname !== '/' && url.pathname !== '/onejav-feed.xml') {
      return new Response('Not found', { status: 404 });
    }
    try {
      const items = await fetchItems();
      return new Response(buildRSS(items), {
        headers: {
          'Content-Type': 'application/rss+xml; charset=utf-8',
          'Cache-Control': 'public, max-age=1800', // 边缘缓存 30 分钟
        },
      });
    } catch (e) {
      return new Response('订阅更新失败: ' + e.message, { status: 502 });
    }
  },
};
