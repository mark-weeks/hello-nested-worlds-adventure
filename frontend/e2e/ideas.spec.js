import { expect, test } from '@playwright/test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdir, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';

const repo = path.resolve(import.meta.dirname, '../..');
const python = process.env.ENFOLDED_PYTHON || 'python';
const key = 'nw_' + 'a'.repeat(32);
const headers = {'X-Beta-Key': key};
const evidence = path.join(tmpdir(), 'enfolded-ideas-evidence');
async function capture(page, name) {
  await mkdir(evidence, {recursive: true});
  await page.screenshot({path: path.join(evidence, name + '.png'), fullPage: true});
}
async function start(promoted = false) {
  const directory = await mkdtemp(path.join(tmpdir(), 'enfolded-ideas-browser-'));
  const child = spawn(python, ['-u','-c', `
import sys
from pathlib import Path
import persistence as db
db._DB_PATH=Path(sys.argv[1])/'worlds.db'
db.mint_invite_key('nw_'+'a'*32,'Ada')
db.mint_invite_key('nw_'+'b'*32,'Bea')
if sys.argv[2]=='promoted':
    from persistence import ideas
    from server import idea_promotion as p
    idea=ideas.submit('nw_'+'a'*32,{'title':'A clearer destination cue','description':'A private report detail.', 'request_id':'fixture-idea'})['id']
    data={field:'A reviewed public requirement.' for field in p.FIELDS}
    data.update(public_title='Improve crossing cues',reviewed=True)
    intent=p.prepare(idea,data,operator='Fixture operator')
    class FakeGitHub:
        def matches(self,*args): return []
        def create(self,repository,title,body): return {'number':321,'body':body}
    p.publish(idea,intent['review_hash'],operator='Fixture operator',github=FakeGitHub())
    ideas.moderate(idea,operator='Fixture operator',explanation='Merged; a playable release is still pending.',status='merged')
from server import _Handler,_ThreadedServer
server=_ThreadedServer(('127.0.0.1',0),_Handler)
print(server.server_port,flush=True)
server.serve_forever()
`, directory, promoted ? 'promoted' : 'empty'], {cwd: repo, env: {...process.env, NESTED_WORLDS_CANONICAL_SEED:'382',
    NESTED_WORLDS_DISABLE_AI:'1', NESTED_WORLDS_DISABLE_IMAGES:'1'}, stdio:['ignore','pipe','pipe']});
  let stderr = ''; child.stderr.on('data', chunk => { stderr += chunk; });
  const port = await new Promise((resolve,reject) => {
    const timer = setTimeout(() => reject(new Error(stderr || 'Ideas fixture did not start')), 15000);
    child.stdout.once('data', chunk => { clearTimeout(timer); resolve(Number(String(chunk).trim())); });
    child.once('exit', () => { clearTimeout(timer); reject(new Error(stderr)); });
  }).catch(error => { child.kill('SIGKILL'); throw error; });
  return {url:`http://127.0.0.1:${port}`, async close() {
    const ended = once(child,'exit'); child.kill('SIGKILL'); await ended; await rm(directory,{recursive:true,force:true});
  }};
}
async function enter(page, server, route='/ideas') {
  await page.addInitScript(key => {
    localStorage.setItem('nw_beta_key',key);
    localStorage.setItem('nw_player_name','Ada');
    localStorage.setItem('nw_seen_intro','1');
    sessionStorage.setItem('nw_sound_invited','1');
  }, key);
  await page.goto(server.url + route);
}
async function keyboardTo(page, target) {
  for (let i=0;i<60;i++) {
    await page.keyboard.press('Tab');
    if (await target.evaluate(node => node === document.activeElement)) return;
  }
  throw new Error('Could not reach control with keyboard');
}

for (const mobile of [false,true]) {
  for (const route of ['/','/app']) {
    test(`Ideas entry preserves ${route === '/' ? 'map' : 'scene'} game on ${mobile ? 'mobile' : 'desktop'}`, async ({page,context}) => {
      const server = await start();
      try {
        await page.setViewportSize(mobile ? {width:390,height:844} : {width:1440,height:1000});
        await enter(page,server,route);
        const link = page.getByRole('link',{name:'Ideas ↗',exact:true});
        await expect(link).toBeVisible();
        await expect(page.getByRole('link',{name:"Player's Guide ↗",exact:true})).toBeVisible();
        await expect(link).toHaveAttribute('href','/ideas');
        await expect(link).toHaveAttribute('target','_blank');
        await expect.poll(() => page.evaluate(() => localStorage.getItem('nw_last_node'))).not.toBeNull();
        const priorUrl = page.url();
        const priorNode = await page.evaluate(() => localStorage.getItem('nw_last_node'));
        await capture(page,`${route === '/' ? 'map' : 'scene'}-${mobile ? 'mobile' : 'desktop'}`);
        await keyboardTo(page,link);
        const popupPromise = context.waitForEvent('page');
        await page.keyboard.press('Enter');
        const board = await popupPromise;
        await expect(board.locator('#board')).toBeVisible();
        await expect(board.locator('#attribution')).toContainText('Ada');
        expect(board.url()).toBe(server.url+'/ideas');
        expect(page.url()).toBe(priorUrl);
        expect(await page.evaluate(() => localStorage.getItem('nw_last_node'))).toBe(priorNode);
        expect(await board.evaluate(() => window.opener)).toBeNull();
        await board.close();
      } finally { await server.close(); }
    });
  }
  test(`Ideas board ${mobile ? 'mobile' : 'desktop'}: empty, validation, text safety, voting, search and withdrawal`, async ({page}) => {
    const server = await start();
    try {
      await page.setViewportSize(mobile ? {width:390,height:844} : {width:1280,height:900});
      await enter(page,server);
      await expect(page.locator('#results')).toHaveAttribute('aria-busy','false');
      await expect(page.locator('#result-status')).toContainText('No ideas yet');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await capture(page,`board-empty-${mobile ? 'mobile' : 'desktop'}`);
      await page.locator('#submit-button').click();
      await expect(page.locator('#title')).toBeFocused();
      const title = '<img src=x onerror="window.__ideasXss=1">';
      await page.getByLabel('Title',{exact:true}).fill(title);
      await page.getByLabel('Your experience and desired outcome').fill('I want a clearer signal when a crossing opens. <script>window.__ideasXss=1</script>');
      await page.locator('#submit-button').click();
      await expect(page.getByRole('link',{name:'Your stable idea link'})).toBeVisible();
      const submitted = await page.request.get(server.url+'/ideas/list',{headers});
      const data = await submitted.json(); expect(data.ideas).toHaveLength(1);
      await page.getByRole('link',{name:'Your stable idea link'}).click();
      await expect(page.locator('#detail-title')).toHaveText(title);
      expect(await page.evaluate(() => window.__ideasXss)).toBeUndefined();
      expect(await page.locator('#detail img,#results img,#detail script').count()).toBe(0);
      const support = page.getByRole('button',{name:'Support idea',exact:true});
      await support.focus(); await page.keyboard.press('Enter');
      await expect(page.getByRole('button',{name:'Undo support',exact:true})).toHaveAttribute('aria-pressed','true');
      await page.getByRole('button',{name:'Undo support',exact:true}).click();
      await expect(page.getByRole('button',{name:'Support idea',exact:true})).toHaveAttribute('aria-pressed','false');
      await page.getByRole('button',{name:'Most supported',exact:true}).click();
      await expect(page.locator('#results')).toContainText(title);
      await page.getByRole('button',{name:'Your submissions',exact:true}).click();
      await expect(page.locator('#results')).toContainText(title);
      await page.getByLabel('Search ideas',{exact:true}).fill('no match anywhere');
      await page.getByRole('button',{name:'Search',exact:true}).click();
      await expect(page.locator('#result-status')).toContainText('No matching ideas');
      await page.getByLabel('Search ideas',{exact:true}).fill('signal');
      await page.getByRole('button',{name:'Search',exact:true}).click();
      await expect(page.locator('#results')).toContainText(title);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await capture(page,`board-detail-${mobile ? 'mobile' : 'desktop'}`);
      await page.getByRole('button',{name:'Withdraw my idea'}).click();
      await expect(page.getByRole('button',{name:'Keep idea'})).toBeFocused();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('button',{name:'Withdraw my idea'})).toBeFocused();
      await page.getByRole('button',{name:'Withdraw my idea'}).click();
      await page.getByRole('button',{name:'Withdraw idea',exact:true}).click();
      await expect(page.locator('#message')).toContainText('was withdrawn');
      await expect(page.locator('#detail')).toBeHidden();
    } finally { await server.close(); }
  });
}

test('Draft survives rejected and interrupted submissions; retries recover one saved idea', async ({page}) => {
  const server = await start();
  try {
    await enter(page,server); await expect(page.locator('#board')).toBeVisible();
    await page.getByLabel('Title',{exact:true}).fill('A draft that must survive');
    await page.getByLabel('Your experience and desired outcome').fill('My experience stays here.');
    await page.route('**/ideas/submit', route => route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'Please revise the idea.'})}));
    await page.locator('#submit-button').click();
    await expect(page.locator('#message')).toContainText('Please revise');
    await expect(page.locator('#title')).toHaveValue('A draft that must survive');
    await capture(page,'board-validation');
    await page.unroute('**/ideas/submit');
    await page.route('**/ideas/submit', async route => { await route.fetch(); await route.abort(); });
    await page.locator('#submit-button').click();
    await expect(page.locator('#draft-state')).toContainText('may have arrived');
    await expect(page.locator('#title')).toBeDisabled();
    await capture(page,'board-interrupted-submission');
    await page.reload();
    await expect(page.locator('#title')).toHaveValue('A draft that must survive');
    await expect(page.locator('#title')).toBeDisabled();
    await page.unroute('**/ideas/submit');
    await page.getByRole('button',{name:'Retry submission to confirm'}).click();
    await expect(page.locator('#message')).toContainText('Idea submitted');
    expect((await (await page.request.get(server.url+'/ideas/list',{headers})).json()).ideas).toHaveLength(1);
    await page.getByRole('link',{name:'Your stable idea link'}).click();
    await page.route('**/ideas/vote', async route => { await route.fetch(); await route.abort(); });
    await page.getByRole('button',{name:'Support idea',exact:true}).click();
    await expect(page.locator('#message')).toContainText('connection did not finish');
    await expect(page.getByRole('button',{name:'Support idea',exact:true})).toHaveAttribute('aria-pressed','false');
    await page.unroute('**/ideas/vote');
    await page.getByRole('button',{name:'Support idea',exact:true}).click();
    await expect(page.getByRole('button',{name:'Undo support',exact:true})).toBeVisible();
    expect((await (await page.request.get(server.url+'/ideas/list',{headers})).json()).ideas[0].votes).toBe(1);
  } finally { await server.close(); }
});

test('Public shell, loading, network failure and keyboard retry', async ({page}) => {
  const server = await start();
  try {
    await page.goto(server.url+'/ideas');
    await expect(page.locator('#notice')).toBeVisible(); await expect(page.locator('#board')).toBeHidden();
    await page.evaluate(key => localStorage.setItem('nw_beta_key',key),key);
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    await page.route('**/ideas/search',async route => { await gate; await route.abort(); });
    await page.reload();
    await expect(page.locator('#message')).toContainText('Loading ideas');
    await capture(page,'board-loading'); release();
    await expect(page.locator('#message')).toContainText('connection did not finish');
    await capture(page,'board-load-failure');
    await page.unroute('**/ideas/search');
    await page.locator('#retry').focus(); await page.keyboard.press('Enter');
    await expect(page.locator('#board')).toBeVisible();
  } finally { await server.close(); }
});

for (const mobile of [false, true]) {
  test(`Pending receipt survives tab loss and a stale retry on ${mobile ? 'mobile' : 'desktop'}`, async ({page, context}) => {
    const server = await start();
    try {
      await page.setViewportSize(mobile ? {width:390,height:844} : {width:1280,height:900});
      await enter(page, server);
      await expect(page.locator('#board')).toBeVisible();
      await page.getByLabel('Title', {exact:true}).fill('Recover across tabs');
      await page.getByLabel('Your experience and desired outcome').fill('My submitted report should remain recoverable after tab loss.');
      let posts = 0;
      context.on('request', request => { if (new URL(request.url()).pathname === '/ideas/submit') posts++; });
      await page.route('**/ideas/submit', async route => { await route.fetch(); await route.abort(); });
      await page.locator('#submit-button').click();
      await expect(page.locator('#draft-state')).toContainText('may have arrived');
      const stale = await context.newPage();
      await stale.goto(server.url + '/ideas');
      await expect(stale.locator('#title')).toBeDisabled();
      await page.close();
      const recovered = await context.newPage();
      await recovered.setViewportSize(mobile ? {width:390,height:844} : {width:1280,height:900});
      await recovered.goto(server.url + '/ideas');
      await expect(recovered.locator('#title')).toHaveValue('Recover across tabs');
      await expect(recovered.locator('#title')).toBeDisabled();
      await capture(recovered, `board-recovered-${mobile ? 'mobile' : 'desktop'}`);
      // A throttled retry says nothing about whether the first request committed.
      await recovered.route('**/ideas/submit', route => route.fulfill({status:429, contentType:'application/json', body:JSON.stringify({error:'Please retry after the limit resets.'})}));
      await recovered.getByRole('button', {name:'Retry submission to confirm'}).click();
      await expect(recovered.locator('#message')).toContainText('limit resets');
      await expect(recovered.locator('#title')).toBeDisabled();
      await recovered.unroute('**/ideas/submit');
      await recovered.getByRole('button', {name:'Retry submission to confirm'}).click();
      await expect(recovered.locator('#message')).toContainText('Idea submitted');
      // An already open tab must consume the completed receipt, not resurrect it.
      await stale.getByRole('button', {name:'Retry submission to confirm'}).click();
      await expect(stale.locator('#message')).toContainText('Idea submitted');
      expect(posts).toBe(3); // Original, intercepted throttle, and exactly one server retry.
      expect((await (await recovered.request.get(server.url+'/ideas/list',{headers})).json()).ideas).toHaveLength(1);
      const receipts = await recovered.evaluate(() => Object.entries(localStorage).filter(([k]) => k.startsWith('nw_ideas_receipt_')).map(([,v]) => JSON.parse(v)));
      expect(receipts).toHaveLength(1);
      expect(receipts[0].state).toBe('confirmed');
      expect(JSON.stringify(receipts)).not.toContain('Recover across tabs');
      expect(receipts[0]).not.toHaveProperty('payload');
      await stale.close(); await recovered.close();
    } finally { await server.close(); }
  });
}

test('Invalid idea IDs are removed before history updates or API requests', async ({page}) => {
  const server = await start();
  try {
    const invalid = 'nw_do-not-retransmit';
    const requests = [];
    page.on('request', request => { if (!request.isNavigationRequest()) requests.push(request.url()); });
    await page.addInitScript(() => {
      window.__ideaHistory = [];
      const replace = history.replaceState.bind(history);
      history.replaceState = (...args) => { window.__ideaHistory.push(args[2]); return replace(...args); };
    });
    await enter(page, server, '/ideas?id=' + invalid);
    await expect(page.locator('#board')).toBeVisible();
    expect(page.url()).toBe(server.url + '/ideas');
    expect(requests.every(url => !url.includes(invalid))).toBe(true);
    expect((await page.evaluate(() => window.__ideaHistory)).every(url => !url.includes(invalid))).toBe(true);
    await expect(page.locator('#detail')).toBeHidden();
  } finally { await server.close(); }
});

test('Successful retry clears only the previous load error after the board has loaded', async ({page}) => {
  const server = await start();
  try {
    await enter(page, server);
    await expect(page.locator('#board')).toBeVisible();
    await page.route('**/ideas/search', route => route.abort());
    await page.getByRole('button', {name:'Most supported', exact:true}).click();
    await expect(page.locator('#message')).toContainText('connection did not finish');
    await page.unroute('**/ideas/search');
    await page.locator('#retry').focus(); await page.keyboard.press('Enter');
    await expect(page.locator('#result-status')).toContainText('No ideas yet');
    await expect(page.locator('#message')).toBeEmpty();
  } finally { await server.close(); }
});

test('A pending receipt cannot overwrite another account draft or another open tab', async ({page, context}) => {
  const server = await start();
  try {
    await enter(page, server);
    await expect(page.locator('#board')).toBeVisible();
    const other = await context.newPage();
    await other.goto(server.url+'/ideas');
    await expect(other.locator('#board')).toBeVisible();
    await other.getByLabel('Title',{exact:true}).fill('Keep this separate draft');
    await other.getByLabel('Your experience and desired outcome').fill('A second report in an existing tab.');
    await page.getByLabel('Title',{exact:true}).fill('Private pending report');
    await page.getByLabel('Your experience and desired outcome').fill('I want to recover my original receipt.');
    await page.route('**/ideas/submit',async route => { await route.fetch(); await route.abort(); });
    await page.locator('#submit-button').click();
    await expect(page.locator('#draft-state')).toContainText('may have arrived');
    await other.locator('#submit-button').click();
    await expect(other.locator('#message')).toContainText('Another Ideas tab');
    await expect(other.locator('#title')).toHaveValue('Keep this separate draft');
    expect((await (await other.request.get(server.url+'/ideas/list',{headers})).json()).ideas).toHaveLength(1);
    // A different participant on the same browser must not restore this payload.
    await other.evaluate(() => localStorage.setItem('nw_beta_key','nw_'+'b'.repeat(32)));
    await other.reload();
    await expect(other.locator('#attribution')).toContainText('Bea');
    await expect(other.locator('#title')).toHaveValue('');
    await expect(other.locator('#description')).toHaveValue('');
    await other.close();
  } finally { await server.close(); }
});

test('Unavailable durable storage prevents publication and retains the draft', async ({page}) => {
  const server = await start();
  try {
    await enter(page, server);
    await expect(page.locator('#board')).toBeVisible();
    await page.getByLabel('Title',{exact:true}).fill('Retain this draft');
    await page.getByLabel('Your experience and desired outcome').fill('Do not send without a durable retry receipt.');
    await page.evaluate(() => {
      const set = Storage.prototype.setItem;
      Storage.prototype.setItem = function(key,value) {
        if (key.startsWith('nw_ideas_receipt_')) throw new Error('Storage denied');
        return set.call(this,key,value);
      };
    });
    await page.locator('#submit-button').click();
    await expect(page.locator('#message')).toContainText('Browser storage is unavailable');
    await expect(page.locator('#title')).toHaveValue('Retain this draft');
    expect((await (await page.request.get(server.url+'/ideas/list',{headers})).json()).ideas).toHaveLength(0);
  } finally { await server.close(); }
});


test('Reviewed issue link is visible, merged stays distinct from available, and outgoing URLs contain no private data', async ({page,context}) => {
  const server = await start(true);
  try {
    await enter(page,server);
    await page.getByRole('link',{name:'A clearer destination cue',exact:true}).click();
    await expect(page.locator('#detail')).toContainText('Merged — awaiting release');
    await expect(page.locator('#detail')).not.toContainText('Available to play');
    const issue = page.getByRole('link',{name:'Follow the GitHub issue ↗'});
    await expect(issue).toHaveAttribute('href','https://github.com/mark-weeks/hello-nested-worlds-adventure/issues/321');
    await expect(issue).toHaveAttribute('rel','noopener noreferrer');
    let outgoing;
    await context.route('https://github.com/**', async route => {
      outgoing = route.request();
      await route.fulfill({contentType:'text/html',body:'<h1>Local issue-link fixture</h1>'});
    });
    const opened = context.waitForEvent('page'); await issue.click(); const remote = await opened;
    await expect(remote.getByRole('heading',{name:'Local issue-link fixture'})).toBeVisible();
    expect(outgoing.headers()['x-beta-key']).toBeUndefined();
    expect(outgoing.headers().referer).toBeUndefined();
    expect(outgoing.url()).not.toContain(key);
    expect(outgoing.url()).not.toContain('private');
    expect(await remote.evaluate(() => window.opener)).toBeNull();
    await remote.close();
    await capture(page,'board-promoted-merged');
  } finally { await server.close(); }
});
for (const mobile of [false, true]) {
  test(`A distinct tab draft survives reload and earlier-submission recovery on ${mobile ? 'mobile' : 'desktop'}`, async ({page, context}) => {
    const server = await start();
    try {
      await enter(page, server);
      const other = await context.newPage();
      await other.setViewportSize(mobile ? {width:390,height:844} : {width:1280,height:900});
      await other.goto(server.url + '/ideas');
      await expect(other.locator('#board')).toBeVisible();
      await other.locator('#title').fill('Keep my separate draft');
      await other.locator('#description').fill('This unfinished idea belongs to this tab.');
      await other.locator('#credit').check();
      await page.locator('#title').fill('Confirm the earlier idea');
      await page.locator('#description').fill('This idea reached the server before its response was lost.');
      let posts = 0;
      context.on('request', request => { if (new URL(request.url()).pathname === '/ideas/submit') posts++; });
      await page.route('**/ideas/submit', async route => { await route.fetch(); await route.abort(); });
      await page.locator('#submit-button').click();
      await expect(page.locator('#draft-state')).toContainText('may have arrived');
      await page.close();
      await other.reload();
      await expect(other.locator('#other-pending')).toBeVisible();
      await expect(other.locator('#title')).toHaveValue('Keep my separate draft');
      await expect(other.locator('#title')).toBeEditable();
      await expect(other.locator('#description')).toHaveValue('This unfinished idea belongs to this tab.');
      await expect(other.locator('#credit')).toBeChecked();
      expect(await other.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await capture(other, `board-separate-draft-${mobile ? 'mobile' : 'desktop'}`);
      const link = other.getByRole('link', {name:'Confirm the earlier submission in a new tab'});
      await link.focus();
      const opened = context.waitForEvent('page');
      await other.keyboard.press('Enter');
      const recovered = await opened;
      await expect(recovered.locator('#title')).toHaveValue('Confirm the earlier idea');
      expect(await recovered.evaluate(() => window.opener)).toBeNull();
      await recovered.locator('#submit-button').click();
      await expect(recovered.locator('#message')).toContainText('Idea submitted');
      await expect(other.locator('#other-pending')).toBeHidden();
      await other.reload();
      await expect(other.locator('#title')).toHaveValue('Keep my separate draft');
      await expect(other.locator('#description')).toHaveValue('This unfinished idea belongs to this tab.');
      await expect(other.locator('#credit')).toBeChecked();
      await other.locator('#submit-button').click();
      await expect(other.locator('#message')).toContainText('Idea submitted');
      const results = (await (await other.request.get(server.url+'/ideas/list',{headers})).json()).ideas;
      expect(results.map(idea => idea.title).sort()).toEqual(['Confirm the earlier idea','Keep my separate draft']);
      expect(posts).toBe(3);
      await recovered.close(); await other.close();
    } finally { await server.close(); }
  });
}
