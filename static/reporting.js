// One private reporting dialog for both browser clients. Player actions and
// shared history keep their existing surfaces; a report is an operational act.
(function installReporting(root) {
  'use strict';
  if (root.EnfoldedReporting) return;

  const CHAT_UNAVAILABLE = 'Chat is unavailable. Its recording information could not be reached.';
  const REPORT_UNAVAILABLE = 'Reporting is unavailable. Ask the person who invited you for help.';
  const UNCERTAIN = 'The report may have arrived. Retry to confirm it. Your details are kept here.';
  const unavailable = () => ({
    chat: {enabled: false, retention_mode: null, retention_days: null, notice: CHAT_UNAVAILABLE},
    reports: {enabled: false, retention_days: null, notice: REPORT_UNAVAILABLE,
      reasons: [], max_detail_length: null}, contact: '', backup_notice: '', revision: '',
  });
  const text = value => typeof value === 'string';
  const duration = value => Number.isInteger(value) && value > 0;

  function readMetadata(data) {
    if (!data || !data.chat || !data.reports ||
        typeof data.chat.enabled !== 'boolean' || typeof data.reports.enabled !== 'boolean' ||
        !text(data.chat.notice) || !data.chat.notice.trim() ||
        !text(data.reports.notice) || !data.reports.notice.trim() ||
        !text(data.contact) || !text(data.backup_notice) || !text(data.revision) ||
        !Array.isArray(data.reports.reasons)) return null;
    const reasons = data.reports.reasons;
    const chatPolicy = data.chat.retention_days === null &&
      (data.chat.retention_mode === 'until_deleted' ||
        (!data.chat.enabled && data.chat.retention_mode === null));
    if (reasons.some(reason => !reason || !text(reason.value) || !reason.value.trim() ||
        !text(reason.label) || !reason.label.trim()) ||
        new Set(reasons.map(reason => reason.value)).size !== reasons.length ||
        !chatPolicy ||
        (data.reports.enabled && (!duration(data.reports.retention_days) || !reasons.length ||
          !Number.isInteger(data.reports.max_detail_length) ||
          data.reports.max_detail_length < 1 || data.reports.max_detail_length > 2000))) return null;
    return {
      chat: {enabled: data.chat.enabled, retention_days: null, retention_mode: data.chat.retention_mode,
        notice: data.chat.notice},
      reports: {enabled: data.reports.enabled,
        retention_days: duration(data.reports.retention_days) ? data.reports.retention_days : null,
        notice: data.reports.notice, reasons: reasons.map(reason => ({value: reason.value, label: reason.label})),
        max_detail_length: data.reports.enabled ? data.reports.max_detail_length : null},
      contact: data.contact, backup_notice: data.backup_notice, revision: data.revision,
    };
  }

  function normalizeMetadata(data) {
    return readMetadata(data) || unavailable();
  }

  function chatAccessibility(metadata) {
    // A configured policy can be paused without changing its retention
    // disclosure. Other unavailable notices already explain why chat is off.
    const chat = metadata?.chat;
    const showUnavailable = chat?.enabled === false && chat.retention_mode === 'until_deleted';
    return {showUnavailable,
      describedBy: (showUnavailable ? 'chat-availability ' : '') + 'chat-recording-notice'};
  }

  async function submitReport(url, payload, request = root.fetch.bind(root)) {
    let response, data;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      response = await request(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload), cache: 'no-store', signal: controller.signal});
      data = await response.json();
    } catch {
      throw Object.assign(new Error(UNCERTAIN), {uncertain: true});
    } finally { clearTimeout(timeout); }
    if (!response.ok) {
      const message = text(data?.error) && data.error.trim() ? data.error : 'Your report could not be saved. Try again.';
      throw Object.assign(new Error(message), {status: response.status, response, data,
        uncertain: response.status !== 400 && response.status !== 422});
    }
    if (data?.status !== 'received' || !text(data.report_id) || !data.report_id.trim())
      throw Object.assign(new Error(UNCERTAIN), {uncertain: true});
    return {report_id: data.report_id, status: 'received'};
  }

  function createController({withKey, request = root.fetch.bind(root), onPolicy = () => {},
    document = root.document, randomUUID = () => root.crypto.randomUUID()} = {}) {
    let metadata = unavailable(), loading, viewer = null, state = null, dialog, elements, opener;
    let busy = false, generation = 0;
    const node = (tag, content, className) => {
      const result = document.createElement(tag);
      if (content) result.textContent = content;
      if (className) result.className = className;
      return result;
    };
    async function load() {
      if (loading) return loading;
      loading = (async () => {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        try {
          const response = await request('/community', {cache: 'no-store', signal: controller.signal});
          // A transient refresh failure must not revoke a policy already read
          // successfully. Only a valid response can change route availability.
          const next = response.ok ? readMetadata(await response.json()) : null;
          if (next) metadata = next;
        } catch { /* Keep the last valid policy; the first load stays closed. */ }
        finally { clearTimeout(timeout); }
        onPolicy(metadata);
        return metadata;
      })().finally(() => { loading = null; });
      return loading;
    }
    function restoreFocus() {
      const fallback = document.querySelector('[aria-label="Message to travelers"]:not(:disabled)') ||
        [...document.querySelectorAll('summary')].find(item => item.textContent === 'Travelers & chat') ||
        document.getElementById('node-name');
      if (opener?.isConnected && !opener.disabled) opener.focus();
      else fallback?.focus();
    }
    function close() {
      if (dialog?.open) dialog.close();
      if (state?.receipt) state = null;
      restoreFocus();
    }
    function ensureDialog() {
      if (dialog) return;
      dialog = node('dialog', '', 'report-dialog');
      dialog.setAttribute('aria-labelledby', 'report-title');
      const title = node('h2', 'Report a concern'); title.id = 'report-title';
      const target = node('p', '', 'report-target');
      const notice = node('p');
      const backup = node('p');
      const contact = node('p');
      const form = node('form');
      const label = node('label', 'Reason'); label.htmlFor = 'report-reason';
      const reason = node('select'); reason.id = 'report-reason'; reason.required = true;
      const detailLabel = node('label', 'Details (optional)'); detailLabel.htmlFor = 'report-detail';
      const detail = node('textarea'); detail.id = 'report-detail'; detail.rows = 5;
      const status = node('p', '', 'report-status'); status.setAttribute('role', 'status');
      const actions = node('div', '', 'report-actions');
      const submit = node('button', 'Send report'); submit.type = 'submit';
      const cancel = node('button', 'Cancel'); cancel.type = 'button'; cancel.onclick = close;
      actions.append(submit, cancel);
      form.append(label, reason, detailLabel, detail, status, actions);
      dialog.append(title, target, notice, backup, contact, form);
      document.body.append(dialog);
      elements = {target, notice, backup, contact, form, reason, detail, status, submit, cancel};
      reason.onchange = () => { if (state && !state.pending) state.reason = reason.value; };
      detail.oninput = () => { if (state && !state.pending) state.detail = detail.value; };
      form.onsubmit = event => { event.preventDefault(); send(); };
      dialog.addEventListener('keydown', event => {
        if (event.key === 'Escape') event.stopPropagation();
      });
      dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    }
    function render() {
      if (!elements || !state) return;
      const {reports} = metadata;
      elements.target.textContent = state.name ? `About ${state.name}` : 'About this chat message';
      elements.notice.textContent = reports.notice;
      elements.backup.textContent = metadata.backup_notice;
      elements.contact.textContent = metadata.contact ? `Questions or concerns: ${metadata.contact}` : '';
      const chosen = state.reason;
      elements.reason.replaceChildren(node('option', 'Choose a reason'));
      elements.reason.firstChild.value = '';
      for (const item of reports.reasons) {
        const option = node('option', item.label); option.value = item.value; elements.reason.append(option);
      }
      elements.reason.value = chosen;
      elements.detail.value = state.detail;
      // Native maxLength counts UTF-16 units; each permitted Unicode code
      // point may occupy two. The submission fence below counts points.
      if (reports.max_detail_length) elements.detail.maxLength = reports.max_detail_length * 2;
      const frozen = busy || !!state.pending || !!state.receipt;
      elements.reason.disabled = frozen || !reports.enabled;
      elements.detail.disabled = frozen || !reports.enabled;
      elements.submit.disabled = busy || !!state.receipt || !reports.enabled || !viewer;
      elements.submit.textContent = busy ? 'Sending…' : state.pending ? 'Retry report' : 'Send report';
      elements.cancel.textContent = state.receipt || state.pending ? 'Close' : 'Cancel';
      elements.status.textContent = state.message || (!reports.enabled ? REPORT_UNAVAILABLE : '');
    }
    async function send() {
      if (!state || busy || state.receipt || !metadata.reports.enabled) return;
      if (!viewer || state.authentication !== withKey('/reports')) {
        state.message = 'Your invitation changed. Open the original invitation to retry this report.'; render(); return;
      }
      if (!state.pending) {
        if (!metadata.reports.reasons.some(reason => reason.value === state.reason)) {
          state.message = 'Choose a reason for this report.'; render(); elements.reason.focus(); return;
        }
        if (Array.from(state.detail).length > metadata.reports.max_detail_length) {
          state.message = 'Shorten the details before sending.'; render(); elements.detail.focus(); return;
        }
        try {
          state.pending = Object.freeze({request_id: randomUUID(), participant: state.participant,
            evidence_ref: state.evidence_ref, reason: state.reason, detail: state.detail});
        } catch {
          state.message = 'This browser could not prepare the report. Your details are kept here.'; render(); return;
        }
      }
      const selected = state;
      busy = true; state.message = ''; render();
      // Disabling the focused submit button drops native focus to body.
      // Keep it inside the dialog throughout the asynchronous submission.
      if (dialog?.open) elements.cancel.focus();
      try {
        const receipt = await submitReport(withKey('/reports'), selected.pending, request);
        if (state !== selected) return;
        selected.receipt = receipt;
        selected.pending = null;
        selected.message = `Report received. Reference: ${receipt.report_id}`;
      } catch (error) {
        if (state !== selected) return;
        selected.message = error.message;
        if (!error.uncertain) selected.pending = null;
        if (root.EnfoldedParticipation && error.response &&
            (error.status === 428 || (error.status === 503 && error.data?.participation_required))) {
          const accepted = await root.EnfoldedParticipation.recover(error.response, error.data);
          if (accepted && state === selected)
            selected.message = 'The notice is now accepted. Your details are kept. Choose Retry report to submit them.';
        }
      } finally {
        busy = false;
        if (state === selected) {
          render();
          if (dialog?.open) {
            const editable = metadata.reports.reasons.some(reason => reason.value === selected.reason)
              ? elements.detail : elements.reason;
            const target = selected.receipt || !metadata.reports.enabled ? elements.cancel
              : selected.pending ? elements.submit : editable;
            target.focus();
          }
        }
      }
    }
    async function open({participant = null, evidence_ref = null, name = ''} = {}) {
      if (!viewer || (!participant && !evidence_ref)) return;
      ensureDialog();
      const current = ++generation;
      opener = document.activeElement;
      // The authenticated URL identifies this local credential. Keep it
      // only in memory, outside report payloads, storage and diagnostics.
      // Unlike live targeting handles it survives a server restart.
      const authentication = withKey('/reports');
      const same = state && state.participant === participant && state.evidence_ref === evidence_ref && state.authentication === authentication;
      if (state?.pending && !same) {
        state.message = 'A report is awaiting confirmation. Retry it before starting another report.';
      } else if (!same) {
        // A draft belongs to its subject, not to whichever Report control the
        // player opens next. Unknown authors match only the same evidence ref.
        const samePerson = state && (participant && state.participant === participant ||
          !participant && !state.participant && evidence_ref && state.evidence_ref === evidence_ref);
        const previous = samePerson && state.authentication === authentication && !state.receipt ? state : null;
        state = {participant, evidence_ref, name, authentication, reason: previous?.reason || '', detail: previous?.detail || '', pending: null,
          receipt: null, message: ''};
      }
      if (!dialog.open) dialog.showModal();
      render();
      await load();
      if (current !== generation || !dialog.open) return;
      render();
      (metadata.reports.enabled ? elements.reason : elements.cancel).focus();
    }
    return {
      load, open, close,
      setViewer(value) { viewer = value || null; },
      destroy() { generation += 1; if (dialog?.open) dialog.close(); dialog?.remove(); dialog = null; elements = null; },
    };
  }
  root.EnfoldedReporting = {normalizeMetadata, chatAccessibility, submitReport, createController};
})(globalThis);
