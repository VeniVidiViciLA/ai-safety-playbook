/* Pure logic for the risk check and policy generator.
   No network access, no storage. Works in the browser (window.PlaybookLogic)
   and in Node (module.exports) so it can be unit-tested. */
(function (root) {
  'use strict';

  /* ---------- Risk self-assessment ---------- */

  // answers: array of length n, each 0, 1, 2 or null/undefined (unanswered)
  function scoreAnswers(answers, n) {
    var total = 0, answered = 0, twos = [];
    for (var i = 0; i < n; i++) {
      var v = answers[i];
      if (v === 0 || v === 1 || v === 2) {
        total += v; answered++;
        if (v === 2) twos.push(i + 1);
      } else if (v !== null && v !== undefined) {
        throw new Error('Invalid answer value at question ' + (i + 1) + ': ' + v);
      }
    }
    return { total: total, answered: answered, complete: answered === n, max: n * 2, scoredTwo: twos };
  }

  // bands: [{min, max, level, ...}] — inclusive ranges
  function bandFor(total, bands) {
    for (var i = 0; i < bands.length; i++) {
      if (total >= bands[i].min && total <= bands[i].max) return bands[i];
    }
    return null;
  }

  /* ---------- Policy generator ---------- */

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];

  function parseIsoDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    if (!m) return null;
    return { y: +m[1], m: +m[2], d: +m[3] };
  }
  function formatDate(iso) {
    var p = parseIsoDate(iso);
    return p ? MONTHS[p.m - 1] + ' ' + p.d + ', ' + p.y : '';
  }
  // Adds whole months; clamps the day to the end of the target month.
  function addMonths(iso, months) {
    var p = parseIsoDate(iso);
    if (!p) return '';
    var idx = (p.m - 1) + Number(months);
    var y = p.y + Math.floor(idx / 12), m = ((idx % 12) + 12) % 12 + 1;
    var last = new Date(Date.UTC(y, m, 0)).getUTCDate();
    var d = Math.min(p.d, last);
    return y + '-' + String(m).padStart(2, '0') + '-' + String(d).padStart(2, '0');
  }

  function clean(v) { return (v === undefined || v === null) ? '' : String(v).trim(); }

  // Replace the first occurrence of `needle` only.
  function replaceFirst(text, needle, value) {
    var i = text.indexOf(needle);
    return i < 0 ? text : text.slice(0, i) + value + text.slice(i + needle.length);
  }
  function replaceAll(text, needle, value) { return text.split(needle).join(value); }

  /* Builds the list of [placeholder -> value] replacements from form values.
     Empty fields leave the original [PLACEHOLDER] in place. */
  function buildReplacements(v) {
    v = v || {};
    var name = clean(v.ownerName), role = clean(v.ownerRole);
    var ownerTitle = name && role ? name + ', ' + role : (name || role);
    var ownerShort = name && role ? name + ' (' + role + ')' : (name || role);
    var months = clean(v.reviewMonths);
    var eff = clean(v.effectiveDate);
    return {
      company: clean(v.company),
      ownerTitle: ownerTitle,
      ownerShort: ownerShort,
      tools: clean(v.tools).split(/\s*[\n,;]\s*/).filter(Boolean).join(', '),
      toolsLocation: clean(v.toolsLocation),
      requestContact: clean(v.requestContact),
      incidentContact: clean(v.incidentContact),
      reviewMonths: months,
      effective: formatDate(eff),
      nextReview: (eff && months) ? formatDate(addMonths(eff, months)) : '',
      approvalDays: clean(v.approvalDays),
      reportWindow: clean(v.reportWindow),
      trainingMinutes: clean(v.trainingMinutes),
      refresherMonths: clean(v.refresherMonths)
    };
  }

  /* Fills placeholders in the template. Works identically on the Markdown
     source and the pre-rendered HTML (placeholder text is identical in both).
     opts.html: escape values and wrap them in <span class="filled">. */
  function fillTemplate(text, values, opts) {
    opts = opts || {};
    var r = buildReplacements(values);
    var wrap = function (s) {
      return opts.html ? '<span class="filled">' + escapeHtml(s) + '</span>' : s;
    };
    var t = text;
    // Order matters: longer/more specific placeholders first.
    if (r.incidentContact) t = replaceAll(t, '[AI OWNER / CONTACT]', wrap(r.incidentContact));
    if (r.ownerTitle) t = replaceAll(t, '[NAME, TITLE]', wrap(r.ownerTitle));
    if (r.ownerShort) t = replaceAll(t, '[AI OWNER]', wrap(r.ownerShort));
    if (r.company) t = replaceAll(t, '[COMPANY NAME]', wrap(r.company));
    if (r.tools) t = t.replace(/\[LIST TOOLS[^\]]*\]/g, function () { return wrap(r.tools); });
    if (r.toolsLocation) t = replaceAll(t, '[LOCATION]', wrap(r.toolsLocation));
    if (r.requestContact) t = replaceAll(t, '[EMAIL/FORM]', wrap(r.requestContact));
    // Dates: first [DATE] is the effective date, second is the next review.
    if (r.effective) t = replaceFirst(t, '[DATE]', wrap(r.effective));
    if (r.nextReview) {
      // If the effective date was filled, the next remaining [DATE] is "Next review".
      t = replaceFirst(t, '[DATE]', wrap(r.nextReview));
    }
    if (r.reviewMonths) t = replaceAll(t, 'every [6] months', 'every ' + wrap(r.reviewMonths) + ' months');
    if (r.approvalDays) t = replaceAll(t, 'within [5] business days', 'within ' + wrap(r.approvalDays) + ' business days');
    if (r.reportWindow) t = replaceAll(t, 'within [24 hours]', 'within ' + wrap(r.reportWindow));
    if (r.trainingMinutes) t = replaceAll(t, 'about [30] minutes', 'about ' + wrap(r.trainingMinutes) + ' minutes');
    if (r.refresherMonths) t = replaceAll(t, 'every [12] months', 'every ' + wrap(r.refresherMonths) + ' months');
    return t;
  }

  // Unique placeholders still present, e.g. ["[DATE]", "[LOCATION]"]
  function remainingPlaceholders(text) {
    var found = text.match(/\[[A-Z0-9][^\]\n<]*\]/g) || [];
    var seen = {}, out = [];
    found.forEach(function (p) { if (!seen[p]) { seen[p] = 1; out.push(p); } });
    return out;
  }

  // Wrap remaining placeholders in <mark> (HTML preview only).
  function highlightPlaceholders(html) {
    return html.replace(/\[[A-Z0-9][^\]\n<]*\]/g, '<mark class="ph">$&</mark>');
  }

  // Markdown -> readable plain text (for the .txt download).
  function toPlainText(md) {
    return md
      .replace(/^#{1,6}\s+(.*)$/gm, function (_, h) { return h + '\n' + h.replace(/./g, '-'); })
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/(^|[^\w])_(.+?)_(?=[^\w]|$)/g, '$1$2')
      .replace(/^\|(?:\s*-+\s*\|)+\s*$/gm, '')
      .replace(/\n{3,}/g, '\n\n');
  }

  function slugify(s) {
    return clean(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'company';
  }

  var api = {
    scoreAnswers: scoreAnswers, bandFor: bandFor,
    escapeHtml: escapeHtml, formatDate: formatDate, addMonths: addMonths,
    buildReplacements: buildReplacements, fillTemplate: fillTemplate,
    remainingPlaceholders: remainingPlaceholders, highlightPlaceholders: highlightPlaceholders,
    toPlainText: toPlainText, slugify: slugify
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.PlaybookLogic = api;
})(typeof window !== 'undefined' ? window : globalThis);
