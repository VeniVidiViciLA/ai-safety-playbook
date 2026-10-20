/* Interactive AI Risk Self-Assessment. Everything runs in the browser.
   Nothing is sent, stored, or tracked. */
(function () {
  'use strict';
  var L = window.PlaybookLogic;
  var data = JSON.parse(document.getElementById('assessment-data').textContent);
  var form = document.getElementById('assessment-form');
  var n = data.questions.length;
  var scoreEl = document.getElementById('live-score');
  var answeredEl = document.getElementById('live-answered');
  var meterEl = document.getElementById('live-meter');
  var bandItems = document.querySelectorAll('.bands li');
  var resultEl = document.getElementById('result');
  var pendingEl = document.getElementById('result-pending');

  function readAnswers() {
    var out = [];
    for (var i = 1; i <= n; i++) {
      var c = form.querySelector('input[name="q' + i + '"]:checked');
      out.push(c ? Number(c.value) : null);
    }
    return out;
  }

  function linkSections(text) {
    return L.escapeHtml(text).replace(/Section (\d)/g, function (m, d) {
      var s = data.sectionLinks[d];
      return s ? '<a href="' + s + '">' + m + '</a>' : m;
    });
  }

  function renderResult(s) {
    var band = L.bandFor(s.total, data.bands);
    resultEl.dataset.level = band.level;
    var html = '<h2 id="result-heading" tabindex="-1">Your result: <span class="badge ' + band.level.toLowerCase() + '">' +
      band.level + ' RISK</span> <span class="muted">' + s.total + ' / ' + s.max + '</span></h2>';
    html += '<p><strong>What it means:</strong> ' + L.escapeHtml(band.meaning) + '</p>';
    html += '<h3>What to do</h3><ol>';
    band.actions.forEach(function (a) { html += '<li>' + linkSections(a) + '</li>'; });
    html += '</ol>';
    if (s.scoredTwo.length) {
      html += '<h3>Questions you scored 2 (fix these first)</h3><ul>';
      s.scoredTwo.forEach(function (q) {
        html += '<li><strong>Q' + q + '.</strong> ' + L.escapeHtml(data.questions[q - 1].text) + '</li>';
      });
      html += '</ul>';
    } else {
      html += '<p class="muted">You didn\u2019t score 2 on any question. Nice work.</p>';
    }
    html += '<p class="muted">Re-take this check after you follow the plan (the playbook suggests re-scoring each quarter). ' +
      'Next steps: <a href="policy.html">fill in your AI policy</a> and follow the <a href="' + data.sectionLinks['5'] + '">30-day rollout plan</a>.</p>';
    html += '<div class="btn-row no-print"><button type="button" class="btn" data-action="print">Print / save as PDF</button>' +
      '<button type="button" class="btn secondary" data-action="reset">Start over</button></div>';
    resultEl.innerHTML = html;
  }

  var wasComplete = false;
  function update() {
    var answers = readAnswers();
    var s = L.scoreAnswers(answers, n);
    scoreEl.textContent = s.total;
    answeredEl.textContent = s.answered + ' of ' + n + ' answered';
    meterEl.style.width = (s.total / s.max * 100) + '%';
    var band = L.bandFor(s.total, data.bands);
    bandItems.forEach(function (li) { li.classList.toggle('current', s.answered > 0 && li.dataset.level === band.level); });
    answers.forEach(function (v, i) {
      document.getElementById('q' + (i + 1) + '-fieldset').classList.toggle('answered', v !== null);
    });
    if (s.complete) {
      renderResult(s);
      resultEl.hidden = false; pendingEl.hidden = true;
      if (!wasComplete && update.userAction) {
        var h = document.getElementById('result-heading');
        h.scrollIntoView({ behavior: 'smooth', block: 'start' });
        h.focus({ preventScroll: true });
      }
    } else {
      resultEl.hidden = true; pendingEl.hidden = false;
      pendingEl.textContent = 'Answer all ' + n + ' questions to see your risk level and action plan (' + (n - s.answered) + ' to go).';
    }
    wasComplete = s.complete;
    return s;
  }

  function reset() {
    form.reset();
    wasComplete = false;
    update.userAction = false;
    update();
    if (history.replaceState) history.replaceState(null, '', location.pathname);
    window.scrollTo(0, 0);
    var first = form.querySelector('input');
    if (first) first.focus();
  }

  form.addEventListener('change', function () { update.userAction = true; update(); });
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('[data-action]');
    if (!a) return;
    if (a.dataset.action === 'print') window.print();
    if (a.dataset.action === 'reset') reset();
  });

  // ?demo=1 (or demo=low|medium|high) pre-fills sample answers for previews/screenshots.
  var demo = new URLSearchParams(location.search).get('demo');
  if (demo) {
    var sets = data.demo;
    var pick = sets[demo] || sets.medium;
    pick.forEach(function (v, i) {
      var el = form.querySelector('input[name="q' + (i + 1) + '"][value="' + v + '"]');
      if (el) el.checked = true;
    });
  }
  update();
  window.__assessment = { update: update, reset: reset, readAnswers: readAnswers };
})();
