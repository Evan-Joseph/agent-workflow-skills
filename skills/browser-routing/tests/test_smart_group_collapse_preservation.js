// Regression test for Smart Tab-Group Collapse Preservation in `chrome_cdp_daemon.js`:
// Verifies that:
// 1) Pure unit contract `computeDesiredGroupCollapsed` collapses new background groups (`true`),
//    while preserving expanded state (`false`) whenever `existingGroupCollapsed === false`,
//    `hasActiveTabInGroup === true`, `targetTabActive === true`, `keepForUser === true`, or `foreground === true`.
// 2) End-to-end daemon + Extension Service Worker:
//    - Opening a pure background task creates a `collapsed: true` tab group;
//    - Opening a `--keep-for-user` task creates a `collapsed: false` tab group;
//    - User manually expanding a collapsed group (`collapsed: false` in Chrome) and Agent opening
//      a second tab OR child `openerId` popup in that same group NEVER re-collapses it (`collapsed: false`);
//    - Having an `active: true` tab inside a group keeps the group `collapsed: false` on subsequent tab additions/reuses.

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const DAEMON_SCRIPT = path.join(os.homedir(), '.agents', 'scripts', 'chrome_cdp_daemon.js');
const { computeDesiredGroupCollapsed } = require(DAEMON_SCRIPT);
const EXT_ID = 'dpccigpgfdgoljglokjhlokmdnjfpfcl';

// --- Part 1: Pure deterministic truth-table assertions ---
assert.strictEqual(computeDesiredGroupCollapsed({}), true, 'default background new group should collapse');
assert.strictEqual(
  computeDesiredGroupCollapsed({ existingGroupCollapsed: true, hasActiveTabInGroup: false }),
  true,
  'already-collapsed background group with no active tab stays collapsed'
);
assert.strictEqual(
  computeDesiredGroupCollapsed({ existingGroupCollapsed: false, hasActiveTabInGroup: false }),
  false,
  'already-expanded group must NOT be forcefully re-collapsed'
);
assert.strictEqual(
  computeDesiredGroupCollapsed({ existingGroupCollapsed: true, hasActiveTabInGroup: true }),
  false,
  'group containing an active tab must NOT be collapsed'
);
assert.strictEqual(
  computeDesiredGroupCollapsed({ targetTabActive: true }),
  false,
  'active target tab must NOT be collapsed'
);
assert.strictEqual(
  computeDesiredGroupCollapsed({ keepForUser: true }),
  false,
  'keepForUser group must stay expanded for user inspection'
);
assert.strictEqual(
  computeDesiredGroupCollapsed({ foreground: true }),
  false,
  'foreground tab group must stay expanded'
);

// --- Part 2: End-to-end spawned daemon + Mock Chrome Service Worker ---
function createMockChromeServer() {
  const state = {
    nextTabId: 200,
    nextGroupId: 500001,
    nextSessionSeq: 1,
    tabs: new Map([
      [
        'PERSONAL_ACTIVE_TAB',
        {
          targetId: 'PERSONAL_ACTIVE_TAB',
          tabId: 100,
          windowId: 1,
          url: 'https://linux.do/',
          title: 'LinuxDO',
          groupId: -1,
          active: true,
        },
      ],
    ]),
    groups: new Map(),
    swTargetId: 'SW_GROUPER_TARGET_1',
    sessions: new Map(),
  };

  function sendWsText(socket, obj) {
    const payload = Buffer.from(JSON.stringify(obj), 'utf8');
    let header;
    if (payload.length < 126) {
      header = Buffer.from([0x81, payload.length]);
    } else if (payload.length < 65536) {
      header = Buffer.alloc(4);
      header[0] = 0x81;
      header[1] = 126;
      header.writeUInt16BE(payload.length, 2);
    } else {
      header = Buffer.alloc(10);
      header[0] = 0x81;
      header[1] = 127;
      header.writeBigUInt64BE(BigInt(payload.length), 2);
    }
    socket.write(Buffer.concat([header, payload]));
  }

  async function evalSwScript(expression) {
    const chromeMock = {
      debugger: {
        async getTargets() {
          return Array.from(state.tabs.values()).map(t => ({
            id: t.targetId,
            tabId: t.tabId,
            type: 'page',
            url: t.url,
            title: t.title,
          }));
        },
      },
      tabs: {
        async query(filter = {}) {
          let list = Array.from(state.tabs.values());
          if (typeof filter.groupId === 'number') {
            list = list.filter(t => t.groupId === filter.groupId);
          }
          return list.map(t => ({
            id: t.tabId,
            windowId: t.windowId,
            groupId: t.groupId,
            url: t.url,
            title: t.title,
            active: Boolean(t.active),
          }));
        },
        async get(tabId) {
          const hit = Array.from(state.tabs.values()).find(t => t.tabId === tabId);
          if (!hit) throw new Error(`No tab with id: ${tabId}`);
          return {
            id: hit.tabId,
            windowId: hit.windowId,
            groupId: hit.groupId,
            url: hit.url,
            title: hit.title,
            active: Boolean(hit.active),
          };
        },
        async group({ groupId, tabIds }) {
          const gid = typeof groupId === 'number' ? groupId : ++state.nextGroupId;
          if (!state.groups.has(gid)) {
            state.groups.set(gid, { id: gid, windowId: 1, title: '', color: 'grey', collapsed: false });
          }
          for (const tid of tabIds) {
            const hit = Array.from(state.tabs.values()).find(t => t.tabId === tid);
            if (hit) hit.groupId = gid;
          }
          return gid;
        },
        async ungroup(tabIds) {
          const ids = Array.isArray(tabIds) ? tabIds : [tabIds];
          for (const tid of ids) {
            const hit = Array.from(state.tabs.values()).find(t => t.tabId === tid);
            if (hit) {
              const oldGid = hit.groupId;
              hit.groupId = -1;
              if (oldGid > -1 && !Array.from(state.tabs.values()).some(x => x.groupId === oldGid)) {
                state.groups.delete(oldGid);
              }
            }
          }
        },
        async remove(tabIds) {
          const ids = Array.isArray(tabIds) ? tabIds : [tabIds];
          for (const tid of ids) {
            const entry = Array.from(state.tabs.entries()).find(([, t]) => t.tabId === tid);
            if (!entry) continue;
            const [targetId, tab] = entry;
            const oldGid = tab.groupId;
            state.tabs.delete(targetId);
            if (oldGid > -1 && !Array.from(state.tabs.values()).some(x => x.groupId === oldGid)) {
              state.groups.delete(oldGid);
            }
          }
        },
      },
      tabGroups: {
        async query() {
          return Array.from(state.groups.values()).map(g => ({ ...g }));
        },
        async update(groupId, props) {
          const g = state.groups.get(groupId);
          if (!g) throw new Error(`No group with id: ${groupId}`);
          Object.assign(g, props);
          return { ...g };
        },
      },
    };
    const fn = new Function('chrome', `return (${expression});`);
    return await fn(chromeMock);
  }

  const server = http.createServer((req, res) => {
    res.writeHead(200);
    res.end('ok');
  });

  server.on('upgrade', (req, socket) => {
    const key = req.headers['sec-websocket-key'];
    const accept = crypto
      .createHash('sha1')
      .update(key + '<EXAMPLE_UUID>')
      .digest('base64');
    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      `Sec-WebSocket-Accept: ${accept}\r\n\r\n`
    );

    let buf = Buffer.alloc(0);
    socket.on('data', async (chunk) => {
      buf = Buffer.concat([buf, chunk]);
      while (buf.length >= 2) {
        const b1 = buf[1];
        const masked = (b1 & 0x80) !== 0;
        let len = b1 & 0x7f;
        let offset = 2;
        if (len === 126) {
          if (buf.length < 4) return;
          len = buf.readUInt16BE(2);
          offset = 4;
        } else if (len === 127) {
          if (buf.length < 10) return;
          len = Number(buf.readBigUInt64BE(2));
          offset = 10;
        }
        const maskLen = masked ? 4 : 0;
        if (buf.length < offset + maskLen + len) return;
        const mask = masked ? buf.slice(offset, offset + 4) : null;
        const data = Buffer.from(buf.slice(offset + maskLen, offset + maskLen + len));
        buf = buf.slice(offset + maskLen + len);
        if (masked) {
          for (let i = 0; i < data.length; i++) data[i] ^= mask[i % 4];
        }
        let msg;
        try {
          msg = JSON.parse(data.toString('utf8'));
        } catch {
          continue;
        }
        const { id, method, params = {}, sessionId } = msg;
        if (method === 'Target.setDiscoverTargets') {
          sendWsText(socket, { id, result: {} });
        } else if (method === 'Target.getTargets') {
          const targetInfos = [
            ...Array.from(state.tabs.values()).map(t => ({
              targetId: t.targetId,
              type: 'page',
              title: t.title,
              url: t.url,
              attached: false,
              ...(t.openerId ? { openerId: t.openerId } : {}),
            })),
            {
              targetId: state.swTargetId,
              type: 'service_worker',
              title: 'Agent Grouper SW',
              url: `chrome-extension://${EXT_ID}/background.js`,
              attached: false,
            },
          ];
          sendWsText(socket, { id, result: { targetInfos } });
        } else if (method === 'Target.attachToTarget') {
          const sid = `sess_${++state.nextSessionSeq}`;
          state.sessions.set(sid, params.targetId);
          sendWsText(socket, { id, result: { sessionId: sid } });
        } else if (method === 'Target.detachFromTarget') {
          state.sessions.delete(params.sessionId);
          sendWsText(socket, { id, result: {} });
        } else if (method === 'Page.navigate') {
          const tid = state.sessions.get(sessionId);
          const tab = state.tabs.get(tid);
          if (tab && params.url) tab.url = params.url;
          sendWsText(socket, { id, sessionId, result: { frameId: tid } });
        } else if (method === 'Target.createTarget') {
          const tid = `TARGET_NEW_${++state.nextTabId}`;
          state.tabs.set(tid, {
            targetId: tid,
            tabId: state.nextTabId,
            windowId: 1,
            url: params.url || 'about:blank',
            title: params.url || 'New',
            groupId: -1,
            active: false,
          });
          sendWsText(socket, { id, result: { targetId: tid } });
        } else if (method === 'Target.closeTarget') {
          state.tabs.delete(params.targetId);
          sendWsText(socket, { id, result: { success: true } });
        } else if (method === 'Runtime.evaluate') {
          const tid = state.sessions.get(sessionId);
          if (tid === state.swTargetId) {
            try {
              const val = await evalSwScript(params.expression);
              sendWsText(socket, { id, sessionId, result: { result: { type: typeof val, value: val } } });
            } catch (e) {
              sendWsText(socket, { id, sessionId, error: { message: e.message } });
            }
          } else {
            sendWsText(socket, { id, sessionId, result: { result: { type: 'undefined' } } });
          }
        } else {
          sendWsText(socket, { id, ...(sessionId ? { sessionId } : {}), result: {} });
        }
      }
    });
  });

  return { server, state };
}

function httpJson(port, method, urlPath, bodyObj = null) {
  return new Promise((resolve, reject) => {
    const body = bodyObj ? Buffer.from(JSON.stringify(bodyObj), 'utf8') : null;
    const req = http.request(
      {
        hostname: '127.0.0.1',
        port,
        path: urlPath,
        method,
        headers: body ? { 'Content-Type': 'application/json', 'Content-Length': body.length } : {},
      },
      (res) => {
        const chunks = [];
        res.on('data', c => chunks.push(c));
        res.on('end', () => {
          try {
            resolve({ status: res.statusCode, json: JSON.parse(Buffer.concat(chunks).toString('utf8')) });
          } catch (e) {
            reject(e);
          }
        });
      }
    );
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

(async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-smart-collapse-'));
  const { server, state } = createMockChromeServer();
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const mockCdpPort = server.address().port;

  const probeSrv = http.createServer();
  await new Promise(r => probeSrv.listen(0, '127.0.0.1', r));
  const daemonPort = probeSrv.address().port;
  await new Promise(r => probeSrv.close(r));

  const activePortFile = path.join(tmpDir, 'DevToolsActivePort');
  fs.writeFileSync(activePortFile, `${mockCdpPort}\n/devtools/browser/mock-smart-uuid\n`);

  const daemon = spawn(process.execPath, [DAEMON_SCRIPT], {
    env: {
      ...process.env,
      CDP_PORT: String(mockCdpPort),
      CDP_DAEMON_PORT: String(daemonPort),
      CDP_WS: `ws://127.0.0.1:${mockCdpPort}/devtools/browser/mock-smart-uuid`,
      CDP_ACTIVE_PORT_FILE: activePortFile,
      CDP_STATE_DIR: tmpDir,
      CDP_FORCE_SCREEN_LOCKED: '0',
      CDP_DISABLE_APPROVAL_NOTIFY: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  try {
    // Wait until daemon HTTP server is ready
    for (let i = 0; i < 30; i++) {
      try {
        const h = await httpJson(daemonPort, 'GET', '/health');
        if (h.status === 200) break;
      } catch {}
      await new Promise(r => setTimeout(r, 80));
    }

    // Case 1: Pure background task -> must collapse (`collapsed: true`) even though personal tab is active!
    const bgOpen = await httpJson(daemonPort, 'POST', '/new', {
      url: 'https://example.com/bg-1',
      task: 'task-bg',
      group: '后台调研',
    });
    assert.strictEqual(bgOpen.json.ok, true);
    assert.strictEqual(state.groups.get(bgOpen.json.groupId).collapsed, true, 'new background group must collapse');

    // Case 2: User expands `后台调研` in Chrome -> Agent opens 2nd tab AND child `openerId` popup -> stays `collapsed: false`!
    state.groups.get(bgOpen.json.groupId).collapsed = false;
    const bgOpen2 = await httpJson(daemonPort, 'POST', '/new', {
      url: 'https://example.com/bg-2',
      task: 'task-bg',
      group: '后台调研',
    });
    assert.strictEqual(bgOpen2.json.groupId, bgOpen.json.groupId);
    assert.strictEqual(
      state.groups.get(bgOpen.json.groupId).collapsed,
      false,
      'opening 2nd tab in user-expanded group must NOT re-collapse it'
    );

    // Simulate child `openerId` popup opened from `bgOpen.json.targetId`
    const childTid = 'TARGET_CHILD_POPUP_1';
    state.tabs.set(childTid, {
      targetId: childTid,
      tabId: ++state.nextTabId,
      windowId: 1,
      url: 'https://example.com/child-popup',
      title: 'Child Popup',
      groupId: -1,
      active: false,
      openerId: bgOpen.json.targetId,
    });
    const listAfterChild = await httpJson(daemonPort, 'GET', '/tabs');
    assert.strictEqual(listAfterChild.status, 200);
    assert.strictEqual(
      state.tabs.get(childTid).groupId,
      bgOpen.json.groupId,
      'child popup must inherit parent groupId'
    );
    assert.strictEqual(
      state.groups.get(bgOpen.json.groupId).collapsed,
      false,
      'adopting child openerId popup in expanded group must NOT re-collapse it'
    );

    // Case 3: Group collapsed again, but user clicks/activates one tab inside it -> `reuse: true` must NOT re-collapse!
    state.groups.get(bgOpen.json.groupId).collapsed = true;
    state.tabs.get('PERSONAL_ACTIVE_TAB').active = false;
    state.tabs.get(bgOpen.json.targetId).active = true;

    const reused = await httpJson(daemonPort, 'POST', '/new', {
      url: 'https://example.com/bg-reused',
      task: 'task-bg',
      group: '后台调研',
      reuse: true,
    });
    assert.strictEqual(reused.json.reused, true);
    assert.strictEqual(
      state.groups.get(bgOpen.json.groupId).collapsed,
      false,
      'reusing tab in a group with an active tab must leave group expanded'
    );

    // Case 4: `keepForUser: true` new group -> immediately expanded (`collapsed: false`)
    state.tabs.get(bgOpen.json.targetId).active = false;
    state.tabs.get('PERSONAL_ACTIVE_TAB').active = true;
    const keepOpen = await httpJson(daemonPort, 'POST', '/new', {
      url: 'https://example.com/review',
      task: 'task-review',
      group: '成果审阅',
      keepForUser: true,
    });
    assert.strictEqual(keepOpen.json.ok, true);
    assert.strictEqual(
      state.groups.get(keepOpen.json.groupId).collapsed,
      false,
      'keepForUser group must open expanded'
    );

    console.log('PASS: test_smart_group_collapse_preservation (all 4 scenarios + unit truth-table verified)');
  } finally {
    if (daemon.exitCode === null) {
      daemon.kill('SIGTERM');
      await new Promise((r) => daemon.once('exit', r));
    }
    await new Promise(r => server.close(r));
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
})().catch((err) => {
  console.error('FAIL:', err);
  process.exit(1);
});
