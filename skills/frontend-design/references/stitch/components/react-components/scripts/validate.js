/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

function loadPackage(name) {
  try {
    return require(name);
  } catch (_) {}
  try {
    return require(require.resolve(name, { paths: [process.cwd()] }));
  } catch (_) {}
  try {
    const root = execSync('npm root -g', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
    return require(path.join(root, name));
  } catch (_) {}
  throw new Error(`${name} not found. Run npm install ${name} in the project or npm install -g ${name}.`);
}

const swc = loadPackage('@swc/core');

const HEX_COLOR_REGEX = /#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})\b/;

function collectStringLiterals(node, out = []) {
  if (!node || typeof node !== 'object') return out;
  if (node.type === 'StringLiteral' && typeof node.value === 'string') {
    out.push(node.value);
  } else if (node.type === 'TemplateElement' && typeof node.raw === 'string') {
    out.push(node.raw);
  }
  for (const key in node) {
    if (node[key] && typeof node[key] === 'object') {
      collectStringLiterals(node[key], out);
    }
  }
  return out;
}

async function validateComponent(filePath) {
  if (!filePath) {
    console.error("Usage: node validate.js <component.tsx>");
    process.exit(1);
  }
  const code = fs.readFileSync(filePath, 'utf-8');
  const filename = path.basename(filePath);
  try {
    const ast = await swc.parse(code, { syntax: "typescript", tsx: true });
    let hasInterface = false;
    let tailwindIssues = [];

    console.log("🔍 Scanning AST...");

    const walk = (node) => {
      if (!node) return;
      if (
        (node.type === 'TsInterfaceDeclaration' || node.type === 'TsTypeAliasDeclaration') &&
        node.id?.value?.endsWith('Props')
      ) {
        hasInterface = true;
      }
      if (node.type === 'JSXAttribute' && (node.name?.name === 'className' || node.name?.value === 'className')) {
        const candidates = collectStringLiterals(node.value);
        for (const str of candidates) {
          if (HEX_COLOR_REGEX.test(str)) tailwindIssues.push(str);
        }
      }
      for (const key in node) { if (node[key] && typeof node[key] === 'object') walk(node[key]); }
    };
    walk(ast);

    console.log(`--- Validation for: ${filename} ---`);
    if (hasInterface) {
      console.log("✅ Props declaration found.");
    } else {
      console.error("❌ MISSING: Props interface (must end in 'Props').");
    }

    if (tailwindIssues.length === 0) {
      console.log("✅ No hardcoded hex values found.");
    } else {
      console.error(`❌ STYLE: Found ${tailwindIssues.length} hardcoded hex codes.`);
      tailwindIssues.forEach(hex => console.error(`   - ${hex}`));
    }

    if (hasInterface && tailwindIssues.length === 0) {
      console.log("\n✨ COMPONENT VALID.");
      process.exit(0);
    } else {
      console.error("\n🚫 VALIDATION FAILED.");
      process.exit(1);
    }
  } catch (err) {
    console.error("❌ PARSE ERROR:", err.message);
    process.exit(1);
  }
}

validateComponent(process.argv[2]);
