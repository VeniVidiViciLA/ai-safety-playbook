/* AI Acceptable Use Policy generator. Everything runs in the browser.
   Nothing you type is sent anywhere or stored. */
(function () {
  'use strict';
  var L = window.PlaybookLogic;
  var tpl = JSON.parse(document.getElementById('policy-template').textContent);
  var form = document.getElementById('policy-form');
  var out = document.getElementById('policy-output');
  var remainingEl = document.getElementById('remaining');
  var statusEl = document.getElementById('status');

  function values() {
    var v = {};
    Array.prototype.forEach.call(form.elements, function (el) { if (el.name) v[el.name] = el.value; });
    return v;
  }
  function markdown() { return L.fillTemplate(tpl.markdown, values(), { html: false }); }

  function render() {
    var v = values();
    out.innerHTML = L.highlightPlaceholders(L.fillTemplate(tpl.html, v, { html: true }));
    var left = L.remainingPlaceholders(L.fillTemplate(tpl.markdown, v, { html: false }));
    remainingEl.innerHTML = left.length
      ? '<strong>' + left.length + ' placeholder' + (left.length === 1 ? '' : 's') + ' still to fill</strong> (highlighted in the policy): ' +
        left.map(function (p) { return '<code>' + L.escapeHtml(p) + '</code>'; }).join(' ')
      : '<strong>All placeholders filled.</strong> Review the policy, delete anything that doesn\u2019t fit, and share it.';
  }

  function say(msg) { statusEl.textContent = msg; setTimeout(function () { if (statusEl.textContent === msg) statusEl.textContent = ''; }, 4000); }

  function copy() {
    var text = markdown();
    var fallback = function () {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      var ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
      document.body.removeChild(ta);
      say(ok ? 'Copied to clipboard (Markdown).' : 'Copy failed. Use Download instead.');
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { say('Copied to clipboard (Markdown).'); }, fallback);
    } else { fallback(); }
  }

  function download(ext) {
    var md = markdown();
    var text = ext === 'txt' ? L.toPlainText(md) : md;
    var blob = new Blob([text], { type: (ext === 'txt' ? 'text/plain' : 'text/markdown') + ';charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = L.slugify(values().company) + '-ai-acceptable-use-policy.' + ext;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
    say('Downloaded ' + a.download);
  }

  form.addEventListener('input', render);
  form.addEventListener('change', render);
  form.addEventListener('reset', function () { setTimeout(function () { setToday(); render(); }, 0); });
  form.addEventListener('submit', function (e) { e.preventDefault(); render(); });
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-action]');
    if (!b) return;
    var act = b.dataset.action;
    if (act === 'copy') copy();
    if (act === 'md') download('md');
    if (act === 'txt') download('txt');
    if (act === 'print') {
      document.body.classList.add('print-policy');
      window.print();
      setTimeout(function () { document.body.classList.remove('print-policy'); }, 500);
    }
  });

  function setToday() {
    var d = form.elements.effectiveDate;
    if (d && !d.value) {
      var t = new Date();
      d.value = t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0') + '-' + String(t.getDate()).padStart(2, '0');
    }
  }
  // ?demo=1 pre-fills example values for previews/screenshots.
  if (new URLSearchParams(location.search).get('demo')) {
    var ex = tpl.demo;
    Object.keys(ex).forEach(function (k) { if (form.elements[k]) form.elements[k].value = ex[k]; });
  }
  setToday();
  render();
  window.__policy = { render: render, markdown: markdown };
})();
