// Regression test for transient >HANDSHAKE_FAST_WAIT_MS timeout latching:
// Verifies that when Chrome CDP handshake transiently stalls past HANDSHAKE_FAST_WAIT_MS
// and passive socket closes, `authLatch` enforces its cooldown window (zero popup spam),
// and once `CDP_AUTH_LATCH_COOLDOWN_MS` elapses with screen unlocked, the very next request
// automatically single-flight re-probes, resets `authLatch`, and recovers `connected=true`.

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const DAEMON_SCRIPT = path.join(os.homedir(), '.agents', 'scripts', 'chrome_cdp_daemon.js');

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
          resolve({ status: res.statusCode, json: JSON.parse(Buffer.concat(chunks).toString('utf8')) });
        });
      }
    );
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

(async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-latch-cooldown-'));
  let stallFirstHandshake = true;
  let wsAttemptCount = 0;

  const server = http.createServer((req, res) => {
    res.writeHead(200);
    res.end('ok');
  });

  server.on('upgrade', (req, socket) => {
    wsAttemptCount++;
    if (stallFirstHandshake) {
      // Simulate Chrome swap/wakeup stall > HANDSHAKE_FAST_WAIT_MS without sending 101 yet
      stallFirstHandshake = false;
      socket.on('error', () => {});
      return;
    }

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
    socket.on('data', (chunk) => {
      buf = Buffer.concat([buf, chunk]);
      while (buf.length >= 2) {
        const masked = (buf[1] & 0x80) !== 0;
        let len = buf[1] & 0x7f;
        let offset = 2;
        if (len === 126) {
          if (buf.length < 4) return;
          len = buf.readUInt16BE(2);
          offset = 4;
        }
        const maskLen = masked ? 4 : 0;
        if (buf.length < offset + maskLen + len) return;
        const mask = masked ? buf.slice(offset, offset + 4) : null;
        const data = Buffer.from(buf.slice(offset + maskLen, offset + maskLen + len));
        buf = buf.slice(offset + maskLen + len);
        if (masked) for (let i = 0; i < data.length; i++) data[i] ^= mask[i % 4];
        let msg;
        try { msg = JSON.parse(data.toString('utf8')); } catch { continue; }
        const reply = JSON.stringify({ id: msg.id, result: { targetInfos: [] } });
        const payload = Buffer.from(reply, 'utf8');
        socket.write(Buffer.concat([Buffer.from([0x81, payload.length]), payload]));
      }
    });
  });

  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const mockCdpPort = server.address().port;

  const probe = http.createServer();
  await new Promise(r => probe.listen(0, '127.0.0.1', r));
  const daemonPort = probe.address().port;
  await new Promise(r => probe.close(r));

  const daemon = spawn(process.execPath, [DAEMON_SCRIPT], {
    env: {
      ...process.env,
      CDP_PORT: String(mockCdpPort),
      CDP_DAEMON_PORT: String(daemonPort),
      CDP_WS: `ws://127.0.0.1:${mockCdpPort}/devtools/browser/mock-latch-uuid`,
      CDP_STATE_DIR: tmpDir,
      CDP_FORCE_SCREEN_LOCKED: '0',
      CDP_DISABLE_APPROVAL_NOTIFY: '1',
      CDP_HANDSHAKE_WAIT_MS: '150',
      CDP_PASSIVE_APPROVAL_TTL_MS: '1000',
      CDP_AUTH_LATCH_COOLDOWN_MS: '1600',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  try {
    for (let i = 0; i < 30; i++) {
      try {
        const h = await httpJson(daemonPort, 'GET', '/health');
        if (h.status === 200) break;
      } catch {}
      await new Promise(r => setTimeout(r, 40));
    }

    // 1) First request stalls > 150ms -> latches approval_modal_timeout (503)
    const r1 = await httpJson(daemonPort, 'GET', '/tabs');
    assert.strictEqual(r1.status, 503);
    assert.strictEqual(r1.json.error, 'cdp_remote_debugging_approval_pending');
    assert.strictEqual(wsAttemptCount, 1);

    // 2) Immediate second request within cooldown does NOT open a 2nd WebSocket
    const r2 = await httpJson(daemonPort, 'GET', '/tabs');
    assert.strictEqual(r2.status, 503);
    assert.strictEqual(wsAttemptCount, 1, 'Must never open a 2nd WS during cooldown');

    // 3) Wait for passive socket TTL (1000ms) + cooldown (1600ms total from latch)
    await new Promise(r => setTimeout(r, 1750));

    // 4) Next request automatically single-flight re-probes and connects cleanly!
    const r3 = await httpJson(daemonPort, 'GET', '/tabs');
    assert.strictEqual(r3.status, 200);
    assert.strictEqual(r3.json.ok, true);
    assert.strictEqual(wsAttemptCount, 2);

    const hAfter = await httpJson(daemonPort, 'GET', '/health');
    assert.strictEqual(hAfter.json.connected, true);
    assert.strictEqual(hAfter.json.authBackoff, false);
    assert.strictEqual(hAfter.json.authLatch.active, false);

    console.log('PASS: Auth latch cooldown auto-reprobe verified (zero duplicate WS during cooldown, automatic recovery after cooldown).');
  } finally {
    await new Promise(resolve => {
      daemon.once('exit', resolve);
      daemon.kill('SIGTERM');
    });
    await new Promise(r => server.close(r));
    fs.rmSync(tmpDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 30 });
  }
})().catch((err) => {
  console.error('FAIL:', err);
  process.exit(1);
});
