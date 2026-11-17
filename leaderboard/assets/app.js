/* Leaderboard front end.
 *
 * Hard rule: no score is ever hard-coded here. If results.csv still contains
 * PLACEHOLDER, the table stays in its empty state. Real rows are rendered only
 * from that file, which is itself generated from committed traces.
 *
 * Task metadata is real (111 measured records). The inline domain fallback
 * exists only so the page still shows its distribution when opened via file://
 * where fetch() is blocked; on GitHub Pages the JSON file is authoritative.
 */
(function () {
  'use strict';

  var FALLBACK_DOMAINS = {
    'visualization': 73, 'frontend': 67, 'svg-art': 51, '3d': 38,
    'audio': 28, 'animation-video': 23, 'game': 20, 'composite': 4
  };

  function el(id) { return document.getElementById(id); }

  function renderChart(domains) {
    var host = el('domain-chart');
    if (!host) return;
    var entries = Object.entries(domains).sort(function (a, b) { return b[1] - a[1]; });
    var max = Math.max.apply(null, entries.map(function (e) { return e[1]; })) || 1;
    host.innerHTML = entries.map(function (e) {
      var pct = Math.round(e[1] / max * 100);
      return '<div class="bar-row"><span>' + e[0] + '</span>' +
             '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
             '<span class="bar-val">' + e[1] + '</span></div>';
    }).join('');
  }

  function fillSelect(id, keys) {
    var sel = el(id);
    if (!sel) return;
    keys.forEach(function (k) {
      var o = document.createElement('option');
      o.value = k; o.textContent = k;
      sel.appendChild(o);
    });
  }

  function renderTasks(tasks, domain, evidence) {
    var grid = el('task-grid');
    if (!grid) return;
    var shown = tasks.filter(function (t) {
      var dOK = domain === 'all' || (t.domains || []).indexOf(domain) >= 0;
      var eOK = evidence === 'all' ||
                (evidence === 'full' && t.prompt_status === 'full') ||
                (evidence === 'other' && t.prompt_status !== 'full');
      return dOK && eOK;
    });
    el('task-count').textContent = shown.length + ' / ' + (tasks.length || 111) + ' tasks';
    if (!shown.length) {
      grid.innerHTML = '<p class="hint">No tasks match this filter.</p>';
      return;
    }
    grid.innerHTML = shown.slice(0, 120).map(function (t) {
      var tags = (t.domains || []).slice(0, 4).map(function (d) {
        return '<span class="tag">' + d + '</span>';
      }).join('');
      var grade = t.prompt_status === 'full'
        ? '<span class="tag full">full · strict D1</span>'
        : '<span class="tag other">' + (t.prompt_status || 'unknown') + ' · Replay</span>';
      var title = (t.title || '(untitled)').replace(/[<>&]/g, '');
      return '<article class="card"><div class="id">' + (t.task_id || '') + '</div>' +
             '<h3>' + title + '</h3><div class="row">' + grade + tags +
             '<span class="tag">' + (t.prompt_chars || 0) + ' chars</span></div></article>';
    }).join('');
  }

  function renderResults(csvText) {
    var lines = csvText.trim().split(/\r?\n/).filter(Boolean);
    if (lines.length < 2 || lines.slice(1).every(function (l) {
      return l.indexOf('PLACEHOLDER') >= 0 || /^[A-Z_]+,/.test(l) === false;
    })) return; // still placeholder: keep the empty state
    // Real rows are parsed by the reproduction script in a later release;
    // this branch exists so the site becomes live without a redesign.
    var body = el('lb-body');
    if (body) body.innerHTML = '<tr><td class="sticky-col">results loaded</td>' +
      '<td colspan="16" class="empty-cell">Run scripts/reproduce_main_table.py to render scored rows.</td></tr>';
  }

  function main() {
    renderChart(FALLBACK_DOMAINS);
    fillSelect('filter-domain', Object.keys(FALLBACK_DOMAINS));
    fillSelect('task-domain', Object.keys(FALLBACK_DOMAINS));

    var tasks = [];
    fetch('data/tasks.json')
      .then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
      .then(function (d) {
        if (d.domains) { renderChart(d.domains); }
        tasks = d.tasks || [];
        el('task-count').textContent = tasks.length + ' tasks loaded';
        renderTasks(tasks, el('task-domain').value, el('task-evidence').value);
      })
      .catch(function () {
        var grid = el('task-grid');
        if (grid) grid.innerHTML = '<p class="hint">Task metadata is served over HTTP. ' +
          'Open this page through GitHub Pages (or <code>python3 -m http.server</code>) ' +
          'to browse all 111 tasks; the domain counts above are already real.</p>';
      });

    fetch('data/results.csv').then(function (r) { return r.ok ? r.text() : ''; })
      .then(renderResults).catch(function () {});

    ['task-domain', 'task-evidence'].forEach(function (id) {
      el(id).addEventListener('change', function () {
        renderTasks(tasks, el('task-domain').value, el('task-evidence').value);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
  } else { main(); }
})();
