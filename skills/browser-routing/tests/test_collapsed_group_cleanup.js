// Regression test for Chrome 157 (`Aperitif`) collapsed tab-group single-tab close bug:
// Verifies that when CDP `Target.closeTarget` returns `{success: false}` on a tab inside
// a `collapsed: true` tab group, `chrome_cdp_daemon.js` uncollapses + ungroups + removes
// the tab via the Extension Service Worker (`chrome.tabs.ungroup` + `chrome.tabs.remove`),
// verifies disappearance from `Target.getTargets`, leaves personal tabs untouched, and
// never resurrects closed tabs in `reconcileAgentTabs()`.

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const DAEMON_SCRIPT = path.join(os.homedir(), '.agents', 'scripts', 'chrome_cdp_daemon.js');
const EXT_ID = 'dpccigpgfdgoljglokjhlokmdnjfpfcl';

function createMockChrome157Server() {
  const state = {
    nextTabId: 101,
    nextGroupId: 343063286,
    nextSessionSeq: 1,
    // Pre-seeded with 1 personal tab + 1 zombie collapsed group tab (`京东协议核验`)
    tabs: new Map([
      [
        '94C0217B7EF4A594D1B2D8D8DC09BC34',
        { targetId: '94C0217B7EF4A594D1B2D8D8DC09BC34', tabId: 100, windowId: 1, url: 'chrome://newtab/', title: '新标签页', groupId: -1 },
      ],
      [
        '2206C25F1A21BE7198E06933909E4900',
        { targetId: '2206C25F1A21BE7198E06933909E4900', tabId: 101, windowId: 1, url: 'https://item.jd.com/100012043978.html', title: 'JD', groupId: 343063286 },
      ],
    ]),
    groups: new Map([
      [343063286, { id: 343063286, windowId: 1, title: '京东协议核验', color: 'blue', collapsed: true }],
    ]),
    swTargetId: 'SW_GROUPER_TARGET_1',
    sessions: new Map(), // sessionId -> targetId
    closeTargetRejectedCount: 0,
    swRemoveCount: 0,
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
        async query() {
          return Array.from(state.tabs.values()).map(t => ({
            id: t.tabId,
            windowId: t.windowId,
            groupId: t.groupId,
            url: t.url,
            title: t.title,
          }));
        },
        async get(tabId) {
          const hit = Array.from(state.tabs.values()).find(t => t.tabId === tabId);
          if (!hit) throw new Error(`No tab with id: ${tabId}`);
          return { id: hit.tabId, windowId: hit.windowId, groupId: hit.groupId, url: hit.url, title: hit.title };
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
            if (!entry) throw new Error(`No tab with id: ${tid}`);
            const [targetId, tab] = entry;
            const oldGid = tab.groupId;
            state.tabs.delete(targetId);
            state.swRemoveCount++;
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
        if ((buf[0] & 0x0f) === 0x08) return;
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
          });
          sendWsText(socket, { id, result: { targetId: tid } });
        } else if (method === 'Target.closeTarget') {
          const tab = state.tabs.get(params.targetId);
          if (!tab) {
            sendWsText(socket, { id, result: { success: false } });
          } else {
            const grp = tab.groupId > -1 ? state.groups.get(tab.groupId) : null;
            const groupCount = tab.groupId > -1
              ? Array.from(state.tabs.values()).filter(x => x.groupId === tab.groupId).length
              : 0;
            // Exact Chrome 157 (`Aperitif`) behavior: refuse Target.closeTarget on last tab in a collapsed group!
            if (grp && grp.collapsed && groupCount <= 1) {
              state.closeTargetRejectedCount++;
              sendWsText(socket, { id, result: { success: false } });
            } else {
              state.tabs.delete(params.targetId);
              sendWsText(socket, { id, result: { success: true } });
            }
          }
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
        headers: body
          ? { 'Content-Type': 'application/json', 'Content-Length': body.length }
          : {},
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
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-collapse-test-'));
  const { server, state } = createMockChrome157Server();
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const mockCdpPort = server.address().port;

  // Find a free daemon port
  const probeSrv = http.createServer();
  await new Promise(r => probeSrv.listen(0, '127.0.0.1', r));
  const daemonPort = probeSrv.address().port;
  await new Promise(r => probeSrv.close(r));

  fs.writeFileSync(
    path.join(tmpDir, 'agent-tabs.json'),
    JSON.stringify({
      version: 4,
      managedGroupIds: [343063286],
      tabs: {
        '2206C25F1A21BE7198E06933909E4900': {
          task: '京东协议核验',
          group: '京东协议核验',
          groupId: 343063286,
          chromeTabId: 101,
          collapsed: true,
          resident: false,
          keepForUser: false,
          createdAt: Date.now(),
          lastUsed: Date.now(),
          url: 'https://item.jd.com/100012043978.html',
        },
      },
    })
  );

  const daemon = spawn(process.execPath, [DAEMON_SCRIPT], {
    env: {
      ...process.env,
      CDP_PORT: String(mockCdpPort),
      CDP_DAEMON_PORT: String(daemonPort),
      CDP_WS: `ws://127.0.0.1:${mockCdpPort}/devtools/browser/mock-157-uuid`,
      CDP_STATE_DIR: tmpDir,
      CDP_FORCE_SCREEN_LOCKED: '0',
      CDP_DISABLE_APPROVAL_NOTIFY: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  try {
    for (let i = 0; i < 30; i++) {
      try {
        const h = await httpJson(daemonPort, 'GET', '/health');
        if (h.status === 200) break;
      } catch {}
      await new Promise(r => setTimeout(r, 50));
    }

    // 1) Verify initial /tabs sees personal tab + collapsed `京东协议核验`
    const before = await httpJson(daemonPort, 'GET', '/tabs');
    assert.strictEqual(before.json.agentTabsCount, 1);
    assert.strictEqual(before.json.totalTabs, 2);

    // 2) Cleanup `京东协议核验` (collapsed single-tab group!)
    const clean1 = await httpJson(daemonPort, 'POST', '/cleanup', { task: '京东协议核验' });
    assert.strictEqual(clean1.json.ok, true);
    assert.strictEqual(clean1.json.closedCount, 1);
    assert.strictEqual(clean1.json.remainingAgentTabs, 0);
    assert.ok(state.swRemoveCount >= 1, 'Expected Extension SW chrome.tabs.remove to run');
    assert.strictEqual(state.closeTargetRejectedCount, 0, 'Should remove via SW before hitting Chrome 157 closeTarget bug');

    // 3) Re-query /tabs (triggers reconcileAgentTabs) -> 0 Agent tabs, personal chrome://newtab/ intact!
    const after1 = await httpJson(daemonPort, 'GET', '/tabs');
    assert.strictEqual(after1.json.agentTabsCount, 0, 'Zombie tab must NOT resurrect in reconcileAgentTabs');
    assert.strictEqual(after1.json.totalTabs, 1, 'Personal chrome://newtab/ must remain untouched');
    assert.strictEqual(after1.json.tabs[0].url, 'chrome://newtab/');
    assert.strictEqual(after1.json.tabs[0].isAgentTab, false);

    // 4) Roundtrip: open a brand-new collapsed single-tab group and clean it up
    const opened = await httpJson(daemonPort, 'POST', '/new', {
      url: 'https://example.com/roundtrip',
      task: 'roundtrip-task',
      group: '单页折叠测试',
    });
    assert.strictEqual(opened.json.ok, true);
    assert.strictEqual(opened.json.grouped, true);

    const mid = await httpJson(daemonPort, 'GET', '/tabs');
    assert.strictEqual(mid.json.agentTabsCount, 1);
    const agTab = mid.json.tabs.find(t => t.isAgentTab);
    assert.strictEqual(agTab.collapsed, true);

    const clean2 = await httpJson(daemonPort, 'POST', '/cleanup', { task: 'roundtrip-task' });
    assert.strictEqual(clean2.json.ok, true);
    assert.strictEqual(clean2.json.closedCount, 1);

    const after2 = await httpJson(daemonPort, 'GET', '/tabs');
    assert.strictEqual(after2.json.agentTabsCount, 0);
    assert.strictEqual(after2.json.totalTabs, 1);

    // 5) Restart daemon with a residual `about:blank` collapsed-group orphan (`managedGroupIds: [343063286]`, `tabs: {}`)
    //    and verify `onopen -> reconcileAgentTabs -> runTtlReaper` evicts it automatically on connect!
    await new Promise(resolve => {
      daemon.once('exit', resolve);
      daemon.kill('SIGTERM');
    });
    state.tabs.set('2206C25F1A21BE7198E06933909E4900', {
      targetId: '2206C25F1A21BE7198E06933909E4900',
      tabId: 109,
      windowId: 1,
      url: 'about:blank',
      title: 'about:blank',
      groupId: 343063286,
    });
    state.groups.set(343063286, { id: 343063286, windowId: 1, title: '京东协议核验', color: 'blue', collapsed: true });
    fs.writeFileSync(
      path.join(tmpDir, 'agent-tabs.json'),
      JSON.stringify({ version: 4, managedGroupIds: [343063286], tabs: {} })
    );

    const daemon2 = spawn(process.execPath, [DAEMON_SCRIPT], {
      env: {
        ...process.env,
        CDP_PORT: String(mockCdpPort),
        CDP_DAEMON_PORT: String(daemonPort),
        CDP_WS: `ws://127.0.0.1:${mockCdpPort}/devtools/browser/mock-157-uuid`,
        CDP_STATE_DIR: tmpDir,
        CDP_FORCE_SCREEN_LOCKED: '0',
        CDP_DISABLE_APPROVAL_NOTIFY: '1',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    try {
      for (let i = 0; i < 30; i++) {
        try {
          const h = await httpJson(daemonPort, 'GET', '/health');
          if (h.status === 200) break;
        } catch {}
        await new Promise(r => setTimeout(r, 50));
      }
      // Trigger lazy connect via /tabs, then wait 150ms for onopen post-connect reaper
      await httpJson(daemonPort, 'GET', '/tabs');
      await new Promise(r => setTimeout(r, 180));
      const afterReconnect = await httpJson(daemonPort, 'GET', '/tabs');
      assert.strictEqual(afterReconnect.json.agentTabsCount, 0, 'onopen reaper must auto-evict about:blank collapsed orphan');
      assert.strictEqual(afterReconnect.json.totalTabs, 1);
      assert.strictEqual(afterReconnect.json.tabs[0].url, 'chrome://newtab/');
    } finally {
      await new Promise(resolve => {
        daemon2.once('exit', resolve);
        daemon2.kill('SIGTERM');
      });
    }

    console.log('PASS: Chrome 157 collapsed single-tab group cleanup & onopen orphan auto-eviction verified.');
  } finally {
    if (daemon.exitCode === null && daemon.signalCode === null) {
      await new Promise(resolve => {
        daemon.once('exit', resolve);
        daemon.kill('SIGTERM');
      });
    }
    await new Promise(r => server.close(r));
    fs.rmSync(tmpDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 30 });
  }
})().catch((err) => {
  console.error('FAIL:', err);
  process.exit(1);
});
