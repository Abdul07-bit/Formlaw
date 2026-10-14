'use strict';

var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
var DATE_RE = new RegExp('\\b\\d{1,2} (?:' + MONTHS.join('|') + ') \\d{4}\\b', 'g');
var MONEY_RE = /[$\u20B9\u20AC\u00A3]\s?\d[\d,]*(?:\.\d+)?/g;
var PAY_RE = /payment|payable|price|invoice|total|amount|fee|\bpay\b/i;
var DELIVER_RE = /deliver|ship/i;
var INJECT_RE = /(ignore|disregard)\s+(all\s+|any\s+)?(previous|prior|above)\s+instructions|reveal\s+.{0,40}(prompt|instructions)/i;
var STOP = ['the', 'and', 'for', 'are', 'was', 'were', 'what', 'when', 'where', 'who', 'which', 'how', 'does', 'did', 'this', 'that', 'with', 'from', 'have', 'has', 'about', 'any', 'all'];

var SAMPLE = [
  { name: 'supply-agreement.txt', text: 'Supply Agreement between Northfield Traders and Meridian Foods.\nClause 4. The total payment amount for the first order is $48,000, payable within 30 days of invoice.\nClause 6. Supplier shall complete delivery by 10 June 2024.\nClause 9. Late payments accrue interest at 1.5% per month.' },
  { name: 'meridian-email.txt', text: 'From: Meridian Foods, purchasing\nSubject: Revised packaging\nWe agreed the final payment amount is $52,000 because of the added packaging scope.\nPlease confirm delivery by 12 June 2024 so our warehouse can plan receiving.' },
  { name: 'invoice-0042.txt', text: 'Invoice 0042 dated 3 May 2024.\nPayment due: $48,000 within 30 days.\nGoods are to be delivered to the Meridian warehouse.' }
];

function passages(doc) {
  var out = [];
  doc.text.split(/\n+/).forEach(function (line) {
    line.split(/(?<=[.!?])\s+/).forEach(function (s) {
      s = s.trim();
      if (s) out.push({ doc: doc.name, n: out.length + 1, text: s });
    });
  });
  return out;
}

function allPassages(docs) {
  return docs.reduce(function (a, d) { return a.concat(passages(d)); }, []);
}

function search(docs, question) {
  var tokens = (question.toLowerCase().match(/[a-z0-9$]+/g) || []).filter(function (t) {
    return t.length > 2 && STOP.indexOf(t) === -1;
  });
  if (!tokens.length) return [];
  var scored = allPassages(docs).map(function (p) {
    var low = p.text.toLowerCase();
    var seen = {};
    var score = 0;
    tokens.forEach(function (t) { if (!seen[t] && low.indexOf(t) !== -1) { seen[t] = 1; score++; } });
    return { p: p, score: score };
  }).filter(function (x) { return x.score > 0; });
  scored.sort(function (a, b) { return b.score - a.score; });
  return scored.slice(0, 5).map(function (x) { return x.p; });
}

function dateKey(s) {
  var m = s.match(/^(\d{1,2}) (\w+) (\d{4})$/);
  return Date.UTC(+m[3], MONTHS.indexOf(m[2]), +m[1]);
}

function findDates(docs) {
  var out = [];
  allPassages(docs).forEach(function (p) {
    (p.text.match(DATE_RE) || []).forEach(function (d) { out.push({ value: d, p: p }); });
  });
  out.sort(function (a, b) { return dateKey(a.value) - dateKey(b.value); });
  return out;
}

function findConflicts(docs) {
  var groups = { 'Payment amount': [], 'Delivery date': [] };
  allPassages(docs).forEach(function (p) {
    if (PAY_RE.test(p.text)) {
      (p.text.match(MONEY_RE) || []).forEach(function (v) {
        groups['Payment amount'].push({ key: v.replace(/[\s,]/g, ''), value: v, p: p });
      });
    }
    if (DELIVER_RE.test(p.text)) {
      (p.text.match(DATE_RE) || []).forEach(function (v) {
        groups['Delivery date'].push({ key: v.toLowerCase(), value: v, p: p });
      });
    }
  });
  var out = [];
  Object.keys(groups).forEach(function (label) {
    var keys = {};
    groups[label].forEach(function (e) { keys[e.key] = 1; });
    if (Object.keys(keys).length > 1) out.push({ label: label, entries: groups[label] });
  });
  return out;
}

function findInjections(docs) {
  return allPassages(docs).filter(function (p) { return INJECT_RE.test(p.text); });
}

function init() {
  var $ = function (id) { return document.getElementById(id); };
  var docs = [];
  var pasteCount = 0;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function setStatus(m) { $('status').textContent = m; }
  function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }

  function addDoc(name, text, sample) {
    if (docs.length >= 10) { setStatus('The limit is 10 documents. Remove one to add another.'); return false; }
    var n = name, k = 2;
    while (docs.some(function (d) { return d.name === n; })) { n = name.replace(/(\.[^.]*)?$/, '-' + k + '$1'); k++; }
    docs.push({ name: n, text: text, sample: !!sample });
    return true;
  }

  function renderDocs() {
    var list = $('doclist');
    list.replaceChildren();
    if (!docs.length) { list.appendChild(el('p', 'empty', 'No documents yet. Load the sample case, add text files, or paste text.')); return; }
    docs.forEach(function (d, i) {
      var row = el('div', 'doc');
      row.appendChild(el('span', 'doc-name', d.name));
      if (d.sample) row.appendChild(el('span', 'tag', 'sample'));
      row.appendChild(el('span', 'muted small', plural(passages(d).length, 'passage')));
      var x = el('button', 'x', 'Remove');
      x.type = 'button';
      x.setAttribute('aria-label', 'Remove ' + d.name);
      x.addEventListener('click', function () { docs.splice(i, 1); renderDocs(); $('results').replaceChildren(el('p', 'empty', 'Documents changed. Run the review again.')); });
      row.appendChild(x);
      list.appendChild(row);
    });
  }

  function section(title, cls) {
    var s = el('section', 'res' + (cls ? ' ' + cls : ''));
    s.appendChild(el('h3', null, title));
    return s;
  }

  function quote(p) {
    var b = el('blockquote');
    b.appendChild(el('p', null, p.text));
    b.appendChild(el('cite', null, p.doc + ', passage ' + p.n));
    return b;
  }

  function review() {
    var out = $('results');
    out.replaceChildren();
    if (!docs.length) { setStatus('Add at least one document first.'); return; }
    var q = $('question').value.trim();
    var s;

    var inj = findInjections(docs);
    if (inj.length) {
      s = section('Notice: instruction-like text found', 'warn');
      inj.forEach(function (p) {
        s.appendChild(el('p', null, p.doc + ', passage ' + p.n + ' reads like an instruction to an AI system. FormLaw treats document text as data and did not act on it.'));
      });
      out.appendChild(s);
    }

    s = section('Passages that match your question');
    if (!q) {
      s.appendChild(el('p', 'muted', 'Type a question to see matching passages.'));
    } else {
      var hits = search(docs, q);
      if (!hits.length) s.appendChild(el('p', 'muted', 'No passage matched. Try words that appear in the documents.'));
      hits.forEach(function (p) { s.appendChild(quote(p)); });
    }
    out.appendChild(s);

    s = section('Figures that differ between documents');
    var conf = findConflicts(docs);
    if (!conf.length) {
      s.appendChild(el('p', 'muted', 'No differing payment amounts or delivery dates found. This check covers those two items only.'));
    }
    conf.forEach(function (c) {
      var card = el('div', 'conflict');
      var head = el('div', 'row');
      head.appendChild(el('strong', null, c.label));
      head.appendChild(el('span', 'tag review', 'Needs review'));
      card.appendChild(head);
      var sides = el('div', 'sides');
      c.entries.forEach(function (e) {
        var side = el('div', 'side');
        side.appendChild(el('p', 'val', e.value));
        side.appendChild(quote(e.p));
        sides.appendChild(side);
      });
      card.appendChild(sides);
      card.appendChild(el('p', 'muted small', 'The documents disagree. FormLaw does not choose one. Check the originals.'));
      s.appendChild(card);
    });
    out.appendChild(s);

    s = section('Dates found');
    var ds = findDates(docs);
    if (!ds.length) s.appendChild(el('p', 'muted', 'No dates in the form 10 June 2024 were found.'));
    else {
      var ul = el('ul', 'dates');
      ds.forEach(function (d) {
        var li = el('li');
        li.appendChild(el('strong', null, d.value));
        li.appendChild(el('span', 'muted small', '  ' + d.p.doc + ', passage ' + d.p.n + ': ' + d.p.text));
        ul.appendChild(li);
      });
      s.appendChild(ul);
    }
    out.appendChild(s);

    setStatus('Review finished: read ' + plural(docs.length, 'document') + ' and ' + plural(allPassages(docs).length, 'passage') + '.');
  }

  function loadSample() {
    docs = SAMPLE.map(function (d) { return { name: d.name, text: d.text, sample: true }; });
    $('question').value = 'What is the payment amount and when is delivery?';
    renderDocs();
    review();
  }

  $('open-sample').addEventListener('click', function () { loadSample(); $('workspace').scrollIntoView(); });
  $('load-sample').addEventListener('click', loadSample);
  $('clear-docs').addEventListener('click', function () {
    docs = [];
    renderDocs();
    $('results').replaceChildren(el('p', 'empty', 'Results appear here. Load the sample case to see an example.'));
    setStatus('All documents removed.');
  });
  $('run').addEventListener('click', review);
  $('question').addEventListener('keydown', function (e) { if (e.key === 'Enter') review(); });

  $('add-paste').addEventListener('click', function () {
    var t = $('paste').value.trim();
    if (!t) { setStatus('Paste some text first.'); return; }
    if (t.length > 1000000) { setStatus('Pasted text is larger than 1 MB.'); return; }
    pasteCount++;
    if (addDoc('pasted-text-' + pasteCount + '.txt', t, false)) { $('paste').value = ''; renderDocs(); setStatus('Pasted text added.'); }
  });

  $('files').addEventListener('change', function (e) {
    var input = e.target;
    var list = Array.prototype.slice.call(input.files);
    if (!list.length) return;
    var msgs = [];
    var pending = list.length;
    function done() {
      pending--;
      if (pending === 0) { renderDocs(); setStatus(msgs.length ? msgs.join(' ') : 'Files added.'); input.value = ''; }
    }
    list.forEach(function (f) {
      if (!/\.(txt|md|csv)$/i.test(f.name)) { msgs.push(f.name + ' skipped: only .txt, .md and .csv files are supported right now.'); done(); return; }
      if (f.size > 1000000) { msgs.push(f.name + ' skipped: larger than 1 MB.'); done(); return; }
      var r = new FileReader();
      r.onload = function () { addDoc(f.name, String(r.result), false); done(); };
      r.onerror = function () { msgs.push(f.name + ' could not be read.'); done(); };
      r.readAsText(f);
    });
  });

  renderDocs();
}

if (typeof document !== 'undefined') init();
if (typeof module !== 'undefined') module.exports = { SAMPLE: SAMPLE, passages: passages, search: search, findDates: findDates, findConflicts: findConflicts, findInjections: findInjections };
