import {describe, expect, it, vi} from 'vitest';
import '../../../static/reporting.js';

const {normalizeMetadata, chatAccessibility, submitReport, createController} = globalThis.EnfoldedReporting;
const metadata = () => ({
  chat: {enabled: true, retention_mode: 'until_deleted', retention_days: null, notice: 'Fixture chat notice.'},
  reports: {enabled: true, retention_days: 1, notice: 'Fixture report notice.',
    reasons: [{value: 'harassment', label: 'Harassment or bullying'}], max_detail_length: 2000},
  contact: 'Fixture operator', backup_notice: 'Fixture backup notice.', revision: 'fixture-revision',
});
const payload = Object.freeze({request_id: 'fixture-request', participant: null,
  evidence_ref: 'opaque-fixture-evidence', reason: 'harassment', detail: 'Private fixture details.'});

describe('chat accessible descriptions', () => {
  it.each([null, normalizeMetadata(null),
    {chat: {enabled: true, retention_mode: 'until_deleted', retention_days: null}},
    {chat: {enabled: false, retention_mode: null, retention_days: null}},
  ])('omits hidden unavailable text for loading, enabled, and unconfigured chat: %j', data => {
    expect(chatAccessibility(data)).toEqual({showUnavailable: false, describedBy: 'chat-recording-notice'});
  });

  it('includes the visible status only when a configured chat policy is paused', () => {
    expect(chatAccessibility({chat: {enabled: false, retention_mode: 'until_deleted', retention_days: null}}))
      .toEqual({showUnavailable: true, describedBy: 'chat-availability chat-recording-notice'});
  });
});

describe('community policy metadata', () => {
  it('keeps the server recording mode, notice, and operator-supplied report duration', () => {
    expect(normalizeMetadata(metadata())).toEqual(metadata());
    const off = metadata();
    off.chat.enabled = off.reports.enabled = false;
    off.chat.retention_mode = null;
    off.chat.retention_days = off.reports.retention_days = null;
    expect(normalizeMetadata(off).chat).toEqual(off.chat);
    expect(normalizeMetadata(off).reports.retention_days).toBeNull();
    expect(normalizeMetadata(off).reports.max_detail_length).toBeNull();
  });

  it('accepts the explicit until-deleted chat policy without inventing an expiry', () => {
    const data = metadata();
    expect(normalizeMetadata(data).chat).toEqual(data.chat);
    const contradictory = metadata();
    contradictory.chat.retention_days = 1;
    expect(normalizeMetadata(contradictory).chat.enabled).toBe(false);
  });

  it('keeps a paused configured policy but rejects timed chat metadata even while disabled', () => {
    const paused = metadata();
    paused.chat.enabled = false;
    expect(normalizeMetadata(paused).chat).toEqual(paused.chat);
    paused.chat.retention_mode = 'days';
    paused.chat.retention_days = 1;
    expect(normalizeMetadata(paused).revision).toBe('');
  });

  it.each([null, {}, {required: false}, {chat: {enabled: true}}])('fails unavailable metadata closed: %j', data => {
    const result = normalizeMetadata(data);
    expect(result.chat.enabled).toBe(false);
    expect(result.reports.enabled).toBe(false);
    expect(result.chat.retention_days).toBeNull();
    expect(result.reports.retention_days).toBeNull();
  });

  it.each([
    ['chat', 'enabled', 1], ['chat', 'retention_days', true], ['chat', 'retention_days', 0],
    ['chat', 'retention_days', 1], ['chat', 'retention_days', undefined],
    ['chat', 'retention_mode', 'days'], ['chat', 'retention_mode', null],
    ['chat', 'retention_mode', undefined], ['chat', 'notice', ''],
    ['reports', 'enabled', 'true'], ['reports', 'retention_days', -1],
    ['reports', 'max_detail_length', 2001], ['reports', 'max_detail_length', true],
    ['reports', 'reasons', []], ['reports', 'reasons', [{value: 'x', label: ''}]],
    ['reports', 'reasons', [{value: 'x', label: 'One'}, {value: 'x', label: 'Two'}]],
  ])('rejects invalid %s.%s rather than inventing a policy', (section, field, value) => {
    const data = metadata(); data[section][field] = value;
    expect(normalizeMetadata(data).chat.enabled).toBe(false);
    expect(normalizeMetadata(data).reports.enabled).toBe(false);
  });

  it('loads public metadata without credentials and shares concurrent reads', async () => {
    let resolve;
    const request = vi.fn(() => new Promise(done => { resolve = done; }));
    const onPolicy = vi.fn();
    const withKey = vi.fn(() => { throw new Error('public read requested a credential'); });
    const controller = createController({request, withKey, onPolicy});
    const one = controller.load(), two = controller.load();
    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith('/community', {cache: 'no-store', signal: expect.any(AbortSignal)});
    resolve({ok: true, json: async () => metadata()});
    expect(await one).toEqual(metadata());
    expect(await two).toEqual(metadata());
    expect(onPolicy).toHaveBeenCalledTimes(1);
    expect(withKey).not.toHaveBeenCalled();
  });

  it.each([
    () => Promise.reject(new TypeError('private network detail')),
    async () => ({ok: false}),
    async () => ({ok: true, json: async () => { throw new SyntaxError('private proxy body'); }}),
  ])('keeps both routes disabled when public metadata cannot be read', async request => {
    const controller = createController({withKey: value => value, request});
    const result = await controller.load();
    expect(result.chat.enabled).toBe(false);
    expect(result.reports.enabled).toBe(false);
    expect(JSON.stringify(result)).not.toContain('private');
  });

  it.each([
    () => Promise.reject(new TypeError('network interruption')),
    async () => ({ok: false, status: 429}),
    async () => ({ok: true, json: async () => { throw new SyntaxError('invalid JSON'); }}),
    async () => ({ok: true, json: async () => ({})}),
  ])('keeps the last valid policy after a failed refresh', async failedRefresh => {
    const request = vi.fn().mockResolvedValueOnce({ok: true, json: async () => metadata()})
      .mockImplementationOnce(failedRefresh);
    const onPolicy = vi.fn();
    const controller = createController({withKey: value => value, request, onPolicy});
    const first = await controller.load();
    expect(first.chat.enabled).toBe(true);
    expect(await controller.load()).toEqual(first);
    expect(onPolicy.mock.calls.at(-1)[0]).toEqual(first);
  });

  it('replaces cached availability only after a valid disabled-policy response', async () => {
    const off = metadata();
    off.chat.enabled = false;
    off.chat.retention_mode = null;
    off.chat.retention_days = null;
    off.chat.notice = 'Chat is unavailable in this world.';
    const request = vi.fn()
      .mockResolvedValueOnce({ok: true, json: async () => metadata()})
      .mockResolvedValueOnce({ok: true, json: async () => off});
    const controller = createController({withKey: value => value, request});
    expect((await controller.load()).chat.enabled).toBe(true);
    expect((await controller.load()).chat).toEqual(off.chat);
  });

  it('bounds a stalled public read and exposes no enabled route', async () => {
    vi.useFakeTimers();
    try {
      const request = vi.fn((_url, {signal}) => new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      }));
      const controller = createController({withKey: value => value, request});
      const result = controller.load();
      await vi.advanceTimersByTimeAsync(5000);
      expect((await result).chat.enabled).toBe(false);
      expect((await result).reports.enabled).toBe(false);
      expect(request.mock.calls[0][1].signal.aborted).toBe(true);
    } finally { vi.useRealTimers(); }
  });
});

describe('private report submissions', () => {
  it('sends exact stable optional nulls and accepts only a received receipt', async () => {
    const request = vi.fn().mockResolvedValue({ok: true,
      json: async () => ({report_id: 'opaque-receipt', status: 'received'})});
    expect(await submitReport('/reports?key=fixture', payload, request))
      .toEqual({report_id: 'opaque-receipt', status: 'received'});
    expect(request).toHaveBeenCalledWith('/reports?key=fixture', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload), cache: 'no-store', signal: expect.any(AbortSignal),
    });
    expect(JSON.parse(request.mock.calls[0][1].body)).not.toHaveProperty('quote');
  });

  it.each([400, 422])('keeps a definitive %i validation refusal editable', async status => {
    const response = {ok: false, status, json: async () => ({error: 'Select the traveler again.'})};
    await expect(submitReport('/reports', payload, async () => response))
      .rejects.toMatchObject({message: 'Select the traveler again.', status, uncertain: false, response});
  });

  it('bounds a stalled request and leaves its frozen payload available for explicit retry', async () => {
    vi.useFakeTimers();
    try {
      const request = vi.fn((_url, {signal}) => new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      }));
      const result = submitReport('/reports', payload, request).catch(error => error);
      await vi.advanceTimersByTimeAsync(15000);
      expect(await result).toMatchObject({uncertain: true});
      expect(request).toHaveBeenCalledTimes(1);
      expect(JSON.parse(request.mock.calls[0][1].body)).toEqual(payload);
      expect(request.mock.calls[0][1].signal.aborted).toBe(true);
    } finally { vi.useRealTimers(); }
  });

  it.each([403, 409, 428, 429, 503])('requires the same receipt retry after status %i', async status => {
    await expect(submitReport('/reports', payload, async () => ({ok: false, status,
      json: async () => ({error: 'A private operational refusal.'})})))
      .rejects.toMatchObject({status, uncertain: true});
  });

  it.each([
    async () => { throw new TypeError('private socket detail'); },
    async () => ({ok: true, json: async () => { throw new SyntaxError('private HTML'); }}),
    async () => ({ok: true, json: async () => ({})}),
    async () => ({ok: true, json: async () => ({report_id: 'receipt', status: 'queued'})}),
    async () => ({ok: true, json: async () => ({report_id: '', status: 'received'})}),
  ])('treats an unreadable or incomplete receipt as uncertain without echoing it', async request => {
    let error;
    try { await submitReport('/reports', payload, request); } catch (caught) { error = caught; }
    expect(error.uncertain).toBe(true);
    expect(error.message).toContain('Retry to confirm');
    expect(error.message).not.toContain('private');
  });
});
