'use strict';
(async () => {
  const $ = selector => document.querySelector(selector);
  const params = new URLSearchParams(location.search);
  const trial = params.get('trial');
  const task = params.get('task');
  const reader = params.get('reader');
  const condition = document.body.dataset.condition;
  const form = $('#signup');
  const controls = [...form.querySelectorAll('[data-field]')];
  const startButton = $('#start'); startButton.disabled = true;
  let expected;
  try {
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(trial || '') || !['talkback','hintback'].includes(reader)) throw new Error('Open this task through the researcher setup page.');
    const response = await fetch('../tasks.json');
    if (!response.ok) throw new Error('Could not load task information.');
    expected = (await response.json())[task];
    if (!expected) throw new Error('Choose a valid dummy data set in task setup.');
  } catch (error) {
    $('#ready p').textContent = error.message; return;
  }
  // Per-page records stay in memory; no entries or logs are sent to a server.
  const events = [];
  let started = null, ended = false, attempts = 0, result = null;
  const metrics = Object.fromEntries(controls.map(c => [c.dataset.field, {dom_focus_count:0,input_events:0,deletion_events:0,first_dom_focus_ms:null,first_input_ms:null,last_input_ms:null}]));
  function log(event, data = {}) {
    const row = {schema_version:1,trial_id:trial,condition,reader,task,event,wall_time_ms:Date.now(),elapsed_ms:started === null ? null : Math.round(performance.now()-started),...data};
    events.push(row);
    // Deliberately contains no entered values. DOM focus is not accessibility focus.
    console.info('HintBackWeb ' + JSON.stringify(row));
    return row;
  }
  function matches(control) {
    if (control.type === 'checkbox') return !control.checked;
    let actual = control.value, wanted = expected[control.dataset.field];
    if (control.type !== 'password') { actual = actual.trim(); wanted = wanted.trim(); }
    if (control.type === 'email') { actual = actual.toLowerCase(); wanted = wanted.toLowerCase(); }
    if (control.type === 'tel') actual = actual.replace(/[\s()-]/g, '');
    return actual === wanted;
  }
  startButton.disabled = false;
  startButton.addEventListener('click', () => {
    if (started !== null) return;
    started = performance.now(); $('#ready').hidden = true; form.hidden = false;
    log('trial_start'); controls[0].focus();
  });
  for (const control of controls) {
    const field = control.dataset.field, metric = metrics[field];
    control.addEventListener('focus', () => {
      if (started === null || ended) return;
      const row = log('dom_focus', {field,control_id:control.id});
      metric.dom_focus_count++; metric.first_dom_focus_ms ??= row.elapsed_ms;
    });
    control.addEventListener('input', e => {
      if (started === null || ended) return;
      const deletion = typeof e.inputType === 'string' && e.inputType.startsWith('delete');
      const row = log('input', {field,input_type:e.inputType || 'selection',matches_expected:matches(control)});
      metric.input_events++; metric.deletion_events += Number(deletion);
      metric.first_input_ms ??= row.elapsed_ms; metric.last_input_ms = row.elapsed_ms;
      // Remove stale errors while editing, without adding an accessible field name.
      control.removeAttribute('aria-invalid'); control.removeAttribute('aria-describedby');
      document.getElementById(control.id + '-error')?.remove();
    });
  }
  function finish(outcome) {
    if (ended) return; ended = true;
    const row = log('trial_end', {outcome,submit_attempts:attempts,field_results:Object.fromEntries(controls.map(c => [c.dataset.field,matches(c)]))});
    result = {schema_version:1,trial_id:trial,condition,reader,task,outcome,duration_ms:row.elapsed_ms,submit_attempts:attempts,field_metrics:metrics,field_results:row.field_results};
    form.hidden = true; $('#result').hidden = false;
    $('#result-title').textContent = outcome === 'completed' ? 'Task completed' : 'Task ended';
    $('#result-message').textContent = outcome === 'completed' ? 'Your entries match the task information. No account was created.' : 'You can now return the phone to the researcher.';
    $('#summary').textContent = `Trial ${trial}: ${outcome}; ${(row.elapsed_ms/1000).toFixed(1)} seconds; ${attempts} submission attempts.`;
    $('#result').focus();
    // Remove fictitious entries from the DOM; the export retains only correctness/events.
    form.reset();
  }
  form.addEventListener('submit', e => {
    e.preventDefault(); if (started === null || ended) return;
    attempts++;
    const wrong = controls.filter(c => !matches(c));
    log('submit_attempt', {attempt:attempts,incorrect_fields:wrong.map(c => c.dataset.field)});
    $('#error-list').replaceChildren(); form.querySelectorAll('.field-error').forEach(e => e.remove());
    controls.forEach(c => { c.removeAttribute('aria-invalid'); c.removeAttribute('aria-describedby'); });
    $('#errors').hidden = !wrong.length;
    if (!wrong.length) { finish('completed'); return; }
    for (const control of wrong) {
      // Same neutral feedback in both versions; does not reveal the missing label/answer.
      const number = controls.indexOf(control) + 1;
      const message = control.type === 'checkbox' ? 'Leave this optional preference unchecked for this task.' : 'Check this entry against your task information.';
      const error = document.createElement('p'); error.id = control.id + '-error'; error.className = 'field-error'; error.textContent = message;
      control.parentElement.append(error); control.setAttribute('aria-invalid','true'); control.setAttribute('aria-describedby',error.id);
      const li = document.createElement('li'), link = document.createElement('a'); link.href = '#' + control.id;
      link.textContent = `Entry ${number}: ${message}`;
      link.addEventListener('click', e => { e.preventDefault(); control.focus(); }); li.append(link); $('#error-list').append(li);
    }
    $('#errors').focus();
  });
  $('#stop').addEventListener('click', () => finish('stopped'));
  $('#download').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify({summary:result,events},null,2)], {type:'application/json'});
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = `${trial}-${condition}-${reader}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  window.addEventListener('beforeunload', e => {
    if (started !== null && !ended) { e.preventDefault(); e.returnValue = ''; }
  });
})();
