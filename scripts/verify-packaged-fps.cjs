// Executes only extracted, actually packaged launch helpers with inert callbacks.
// No application bootstrap, native process, real timer, or filesystem helper runs.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const path = require("node:path");
const ts = require("typescript");
const resourceFile = process.argv[2];
assert(
  resourceFile,
  "Usage: node scripts/verify-packaged-fps.cjs resources.neu [--report output.json] [--assert-baseline-limitation]"
);
const bytes = fs.readFileSync(resourceFile);
const sha256 = value => crypto.createHash("sha256").update(value).digest("hex");
assert(bytes.length >= 16, "ASAR header");
const headerSize = bytes.readUInt32LE(4),
  jsonSize = bytes.readUInt32LE(12);
const bodyOffset = 8 + headerSize;
assert(
  16 + jsonSize <= bodyOffset && bodyOffset <= bytes.length,
  "ASAR header bounds"
);
const archive = JSON.parse(bytes.subarray(16, 16 + jsonSize).toString("utf8"));
const entries = [],
  scripts = [];
function inspect(directory, prefix = "") {
  for (const [name, entry] of Object.entries(directory.files)) {
    assert(
      !name.includes("/") && name !== ".." && name !== ".",
      "ASAR entry name"
    );
    const fullName = prefix + name;
    if (entry.files) {
      inspect(entry, fullName + "/");
      continue;
    }
    const offset = Number(entry.offset),
      size = entry.size;
    assert(
      Number.isSafeInteger(offset) &&
        offset >= 0 &&
        Number.isSafeInteger(size) &&
        size >= 0,
      "ASAR entry bounds"
    );
    assert(bodyOffset + offset + size <= bytes.length, fullName);
    const raw = bytes.subarray(bodyOffset + offset, bodyOffset + offset + size);
    if (entry.integrity) {
      const integrity = entry.integrity;
      assert.equal(integrity.algorithm, "SHA256");
      assert.equal(sha256(raw), integrity.hash, fullName + " integrity");
      assert(
        Number.isSafeInteger(integrity.blockSize) && integrity.blockSize > 0
      );
      const blocks = [];
      for (let pos = 0; pos < raw.length; pos += integrity.blockSize)
        blocks.push(sha256(raw.subarray(pos, pos + integrity.blockSize)));
      assert.deepEqual(blocks, integrity.blocks, fullName + " block integrity");
    }
    entries.push({ path: fullName, sha256: sha256(raw), size });
    if (/^dist\/assets\/[^/]+\.js$/.test(fullName))
      scripts.push({ path: fullName, code: raw.toString("utf8") });
  }
}
inspect(archive);
assert.equal(scripts.length, 1, "One executable frontend bundle");
const inputFile = scripts[0].path,
  code = scripts[0].code;
const ast = ts.createSourceFile(
  inputFile,
  code,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.JS
);
assert.equal(ast.parseDiagnostics.length, 0);
function descendants(node, predicate) {
  const result = [];
  function visit(current) {
    if (predicate(current)) result.push(current);
    ts.forEachChild(current, visit);
  }
  visit(node);
  return result;
}
const functions = descendants(ast, ts.isFunctionDeclaration);
const text = node => node.getText(ast);
const unique = (nodes, label) => {
  assert.equal(nodes.length, 1, label);
  return nodes[0];
};
const smallestFunction = (predicate, label) => {
  const candidates = functions
    .filter(n => predicate(text(n)))
    .sort((a, b) => a.getWidth(ast) - b.getWidth(ast));
  assert(candidates.length, label);
  assert(
    !candidates[1] || candidates[1].getWidth(ast) > candidates[0].getWidth(ast),
    label
  );
  return candidates[0];
};
const launch = smallestFunction(
  s => s.includes("D3DMetal requires a per-game Wine selection."),
  "launchProgram"
);
const start = smallestFunction(
  s => s.includes("Starting unlockfps.exe with target"),
  "startGenshinFpsUnlockScript"
);
const quote = smallestFunction(
  s => s.includes('.replaceAll("\'"'),
  "shellQuote"
);
const delayed = smallestFunction(
  s =>
    s.includes("schedule()") &&
    s.includes("setTimeout(") &&
    s.includes("clearTimeout("),
  "createDelayedCompanion"
);
const dxmt = smallestFunction(
  s =>
    s.includes("DXMT_CONFIG:") && s.includes("`d3d11.preferredMaxFrameRate="),
  "withDxmtPreferredMaxFrameRate"
);
const metal = smallestFunction(
  s =>
    s.includes("delete ") &&
    s.includes('WINE_CPU_TOPOLOGY:"8:0,1,2,3,4,5,6,7"'),
  "withD3DMetalPerformanceEnv"
);
const transform = smallestFunction(
  s => s.includes(".exec2.bind(") && s.includes("finally{"),
  "withWineExec2Transform"
);
const sanitize = smallestFunction(
  s =>
    s.includes("Math.trunc(Number(") &&
    s.includes("Number.isFinite(") &&
    s.includes(".fpsUnlockTarget"),
  "sanitizeFps"
);
const ensure = smallestFunction(
  s =>
    s.includes('"drive_c","fps-unlocker"') &&
    s.includes("DOWNLOADING_ENVIRONMENT_SPEED"),
  "ensureGenshinFpsUnlocker"
);
const calls = n => descendants(n, ts.isCallExpression);
const callName = n => {
  assert(ts.isIdentifier(n.expression), text(n));
  return n.expression.text;
};
const variableForString = value =>
  unique(
    descendants(ast, ts.isVariableDeclaration).filter(
      n =>
        ts.isIdentifier(n.name) &&
        n.initializer &&
        ((ts.isStringLiteral(n.initializer) && n.initializer.text === value) ||
          (value === "dxmt" && text(n.initializer) === defaults + ".renderer"))
    ),
    "constant " + value
  ).name.text;
const defaults = unique(
  descendants(ast, ts.isVariableDeclaration).filter(
    n =>
      ts.isIdentifier(n.name) &&
      n.initializer &&
      text(n.initializer) ===
        '{fpsUnlockEnabled:!0,fpsUnlockTarget:120,renderer:"dxmt"}'
  ),
  "game defaults"
).name.text;
const resolveName = callName(
  unique(
    calls(start).filter(n =>
      n.arguments.some(
        a =>
          ts.isStringLiteral(a) &&
          a.text === "./hoyoplay_genshin_fps_unlocker.sh"
      )
    ),
    "resolve"
  )
);
const writeName = callName(
  unique(
    calls(start).filter(
      n =>
        n.arguments.length === 2 &&
        text(n.arguments[1]).includes('"#!/bin/bash"')
    ),
    "script write"
  )
);
const spawnName = callName(
  unique(
    calls(start).filter(
      n =>
        n.arguments.length === 2 && text(n.arguments[0]).startsWith('["bash",')
    ),
    "companion spawn"
  )
);
const killName = callName(
  unique(
    calls(start).filter(
      n =>
        n.arguments.length === 1 && text(n.arguments[0]).startsWith('["kill",')
    ),
    "companion stop"
  )
);
const wineBinName = callName(
  unique(
    calls(launch).filter(
      n =>
        n.arguments.length === 2 &&
        text(n.arguments[0]).endsWith(".id") &&
        text(n.arguments[1]).endsWith(".wineTag()")
    ),
    "selected Wine bin"
  )
);
const rendererCall = unique(
  calls(launch).filter(
    n =>
      n.arguments.length === 1 &&
      ts.isObjectLiteralExpression(n.arguments[0]) &&
      n.arguments[0].properties.some(p => p.name?.getText(ast) === "github")
  ),
  "ensure D3DMetal runtime"
);
const rendererName = callName(rendererCall);
const ariaName = text(
  unique(
    rendererCall.arguments[0].properties.filter(
      p => p.name?.getText(ast) === "aria2"
    ),
    "aria2"
  ).initializer
);
const githubName = text(
  unique(
    rendererCall.arguments[0].properties.filter(
      p => p.name?.getText(ast) === "github"
    ),
    "github"
  ).initializer
);
const setterCall = unique(
  calls(launch).filter(
    n =>
      ts.isIdentifier(n.expression) &&
      n.arguments.length === 1 &&
      ts.isIdentifier(n.arguments[0]) &&
      ![sanitize.name.text, metal.name.text].includes(n.expression.text)
  ),
  "runtime path setter"
);
const setterName = callName(setterCall);
const extracted = [
  quote,
  start,
  delayed,
  dxmt,
  metal,
  transform,
  sanitize,
  launch,
];
const bindings = Object.fromEntries(
  extracted.map(n => [
    n === launch
      ? "launch"
      : n === start
      ? "start"
      : n === delayed
      ? "delayed"
      : n === dxmt
      ? "dxmt"
      : n === metal
      ? "metal"
      : n === transform
      ? "transform"
      : n === sanitize
      ? "sanitize"
      : "quote",
    n.name.text,
  ])
);
const state = {
  events: [],
  scripts: [],
  spawns: [],
  timers: new Map(),
  serial: 0,
  current: null,
};
const context = {
  [variableForString("dxmt")]: "dxmt",
  [variableForString("d3dmetal")]: "d3dmetal",
  [variableForString("__shared__")]: "__shared__",
  [defaults]: {
    fpsUnlockEnabled: true,
    fpsUnlockTarget: 120,
    renderer: "dxmt",
  },
  [ariaName]: {},
  [githubName]: {},
  [setterName]: () => {},
  [ensure.name.text]: async function* () {
    state.events.push("ensure-release-companion");
  },
  [rendererName]: async function* () {
    state.events.push("ensure-renderer");
    return "/unchanged/renderer";
  },
  [wineBinName]: async (gameId, tag) => {
    assert.equal(gameId, "genshin");
    assert.equal(tag, "11.0-dxmt-signed-with-patches");
    return "/unchanged/per-game-wine/bin/wine";
  },
  [resolveName]: p => p,
  [writeName]: async (file, script) => {
    state.scripts.push({ file, script });
    state.events.push("script-created");
  },
  [spawnName]: async (args, env) => {
    state.spawns.push({ args, env });
    state.events.push("companion-spawn");
    return { id: state.serial, pid: 100 + state.serial };
  },
  [killName]: async () => state.events.push("companion-kill-fallback"),
  Neutralino: {
    os: {
      updateSpawnedProcess: async () => state.events.push("companion-stop"),
    },
  },
  setTimeout: (callback, ms) => {
    assert.equal(ms, 10000);
    const id = ++state.serial;
    state.timers.set(id, callback);
    return id;
  },
  clearTimeout: id => {
    state.timers.delete(id);
    state.events.push("timer-cleared");
  },
};
vm.createContext(context);
vm.runInContext(extracted.map(text).join("\n"), context);
const events = [];
const launchOutputs = new Map();
let cases = 0;
const rates = env =>
  (env.DXMT_CONFIG ?? "")
    .split(";")
    .filter(s => /^\s*d3d11\.preferredMaxFrameRate\s*=/.test(s))
    .map(s => s.slice(s.indexOf("=") + 1).trim());
const unrelated = env =>
  (env.DXMT_CONFIG ?? "")
    .split(";")
    .filter(s => !/^\s*d3d11\.preferredMaxFrameRate\s*=/.test(s));
const baseEnv = Object.freeze({
  DXMT_CONFIG:
    "other.setting=150;d3d11.preferredMaxFrameRate=60;dxgi.customVendorId=1002;",
  DXMT_CONFIG_FILE: "/unchanged/config",
  WINEPREFIX: "/unchanged/prefix",
  MTL_HUD_ENABLED: "1",
  ROSETTA_ADVERTISE_AVX: "1",
  UNRELATED: "retained",
});
const complexEnv = Object.freeze({
  ...baseEnv,
  DXMT_CONFIG:
    "other.setting=150; d3d11.preferredMaxFrameRate = 120 ;d3d11.preferredMaxFrameRate=150;d3d11.preferredMaxFrameRate = -1;other.d3d11.preferredMaxFrameRate=160;d3d11.preferredMaxFrameRateOther=121;dxgi.customVendorId=1002;;",
});
const noRateEnv = Object.freeze({
  ...baseEnv,
  DXMT_CONFIG: "other.setting=150;dxgi.customVendorId=1002;",
});
const absentEnv = Object.freeze({
  WINEPREFIX: "/unchanged/prefix",
  UNRELATED: "retained",
});
const runtime = {
  prefix: "/unchanged/prefix",
  exec2: async (command, args, env, log) => {
    const current = state.current;
    assert.equal(command, "game.exe");
    assert.deepEqual(args, []);
    assert.equal(log, "game.log");
    current.received = env;
    state.events.push("game-exec");
    if (!current.endBeforeTimer) {
      for (const [id, callback] of state.timers) {
        state.timers.delete(id);
        callback();
      }
      await new Promise(setImmediate);
    }
    state.events.push("game-end");
    if (current.fail) throw new Error("mock game failure");
  },
};
async function run({
  target,
  enabled = true,
  renderer = "dxmt",
  input = baseEnv,
  fail = false,
  endBeforeTimer = false,
  gameId = "genshin",
}) {
  state.events = [];
  state.scripts = [];
  state.spawns = [];
  state.timers.clear();
  const original = JSON.stringify(input);
  const normalized = context[sanitize.name.text](String(target));
  const current = (state.current = { fail, endBeforeTimer });
  const game = {
    id: gameId,
    fpsSupported: true,
    fpsEnabled: () => enabled,
    fpsTarget: () => String(target),
    wineRef: { current: runtime },
    renderer: () => renderer,
    wineTag: () => "11.0-dxmt-signed-with-patches",
    config: { saved: "unchanged" },
    client: {
      launch: async function* (config) {
        assert.deepEqual(config, { saved: "unchanged" });
        state.events.push("patch-application");
        yield "supervised";
        try {
          await runtime.exec2("game.exe", [], input, "game.log");
        } finally {
          state.events.push("wine-wait");
          state.events.push("patch-reversion");
        }
      },
    },
  };
  let failure;
  try {
    for await (const yielded of context[launch.name.text](game))
      assert.equal(yielded, "supervised");
  } catch (error) {
    failure = error;
  }
  assert.equal(failure?.message, fail ? "mock game failure" : undefined);
  const hasCompanion = gameId === "genshin" && enabled;
  const writes = hasCompanion && !endBeforeTimer;
  assert.equal(state.spawns.length, writes ? 1 : 0);
  assert.equal(state.scripts.length, writes ? 1 : 0);
  assert.equal(
    state.events.filter(x => x === "companion-stop").length,
    writes ? 1 : 0
  );
  assert.equal(state.timers.size, 0, "No retained delayed companion timer");
  const expectedGameRate =
    enabled && gameId === "genshin" && renderer === "dxmt"
      ? normalized > 60
        ? 0
        : normalized
      : null;
  if (expectedGameRate !== null) {
    assert.deepEqual(rates(current.received), [String(expectedGameRate)]);
    assert.deepEqual(unrelated(current.received), unrelated(input));
    for (const [key, value] of Object.entries(input))
      if (key !== "DXMT_CONFIG")
        assert.equal(current.received[key], value, key);
  } else if (renderer === "d3dmetal") {
    assert.equal(
      JSON.stringify(current.received),
      JSON.stringify(context[metal.name.text](input))
    );
  } else assert.equal(JSON.stringify(current.received), JSON.stringify(input));
  if (writes) {
    const companion = state.spawns[0];
    assert.deepEqual(Array.from(companion.args), [
      "bash",
      "./hoyoplay_genshin_fps_unlocker.sh",
    ]);
    if (renderer === "dxmt") {
      assert.deepEqual(rates(companion.env), [String(normalized)]);
      assert.deepEqual(unrelated(companion.env), unrelated(input));
      for (const [key, value] of Object.entries(input))
        if (key !== "DXMT_CONFIG") assert.equal(companion.env[key], value, key);
      if (normalized > 60)
        assert.notEqual(
          companion.env,
          current.received,
          "Game override must use separate environment"
        );
    } else
      assert.equal(
        JSON.stringify(companion.env),
        JSON.stringify(current.received)
      );
    const script = state.scripts[0].script;
    assert(script.includes("Starting unlockfps.exe with target " + normalized));
    const invocation = script
      .split("\n")
      .filter(
        l =>
          l.includes('"$WINE"') &&
          l.includes("unlockfps.exe") &&
          l.endsWith(" &")
      );
    assert.equal(invocation.length, 1);
    assert(
      invocation[0].endsWith(" " + normalized + " &"),
      "Numeric target argument"
    );
    assert(script.includes("WINE='/unchanged/per-game-wine/bin/wine'"));
    assert(script.includes("export WINEPREFIX='/unchanged/prefix'"));
    assert(script.includes("trap cleanup INT TERM EXIT"));
    assert(script.includes("taskkill.exe /F /IM unlockfps.exe"));
    assert(
      state.events.indexOf("companion-stop") > state.events.indexOf("game-end")
    );
    assert(
      state.events.indexOf("game-exec") <
        state.events.indexOf("companion-spawn"),
      "Original deferred startup ordering"
    );
  }
  assert(state.events.indexOf("wine-wait") > state.events.indexOf("game-end"));
  assert(
    state.events.indexOf("patch-reversion") > state.events.indexOf("wine-wait")
  );
  assert.equal(
    JSON.stringify(input),
    original,
    "Caller environment must not mutate"
  );
  const oldCount = state.spawns.length;
  state.current = { fail: false, endBeforeTimer: true };
  await runtime.exec2("game.exe", [], baseEnv, "game.log");
  assert.equal(
    state.current.received,
    baseEnv,
    "Original Wine exec2 restored after launch"
  );
  assert.equal(state.spawns.length, oldCount);
  events.push({
    target: String(target),
    normalized,
    enabled,
    renderer,
    gameId,
    gameRates: rates(current.received),
    companionRates: writes ? rates(state.spawns[0].env) : null,
    companionArgument: writes ? normalized : null,
    failed: fail,
    endBeforeTimer,
    input:
      input === complexEnv
        ? "duplicate-and-whitespace"
        : input === noRateEnv
        ? "no-rate"
        : input === absentEnv
        ? "absent"
        : "normal",
  });
  if (
    enabled &&
    renderer === "dxmt" &&
    input === baseEnv &&
    !fail &&
    !endBeforeTimer &&
    state.spawns.length
  )
    launchOutputs.set(normalized, {
      game: current.received,
      companion: state.spawns[0].env,
    });
  cases++;
}
async function verifyNativeForwarding() {
  const wineExec = smallestFunction(
    s => s.includes("D3DMetal renderer selected without a library folder."),
    "per-game wineExec2"
  );
  const wineFactory = wineExec.parent.parent;
  assert(ts.isFunctionDeclaration(wineFactory));
  const rootBindings = Object.fromEntries(
    wineFactory.parameters[0].name.elements.map(n => [
      n.propertyName.text,
      n.name.text,
    ])
  );
  const environment = unique(
    descendants(wineFactory, ts.isFunctionDeclaration).filter(
      n =>
        text(n).includes(
          'return{WINEDEBUG:"fixme-all,err-unwind,+timestamp",WINEPREFIX:'
        ) && !text(n).includes("async function")
    ),
    "per-game defaults"
  );
  const taskPolicy = smallestFunction(
    s =>
      s.includes('["taskpolicy","-a","-t","0","-l","0",...') &&
      !s.includes("async function"),
    "per-game task policy"
  );
  const loader = unique(
    wineFactory.body.statements
      .filter(ts.isVariableStatement)
      .flatMap(n => Array.from(n.declarationList.declarations))
      .filter(n => n.initializer && ts.isAwaitExpression(n.initializer)),
    "Wine loader"
  ).name.text;
  const nativeCall = unique(
    calls(wineExec).filter(n => n.arguments.length === 4),
    "native exec2 call"
  );
  const native = unique(
    functions.filter(n => n.name?.text === callName(nativeCall)),
    "native exec2"
  );
  assert(text(native).includes('Neutralino.events.on("spawnedProcess"'));
  const buildCall = unique(
    calls(native).filter(
      n =>
        n.arguments.length === 2 && ts.isArrayLiteralExpression(n.arguments[0])
    ),
    "command builder call"
  );
  const builder = unique(
    functions.filter(n => n.name?.text === callName(buildCall)),
    "command builder"
  );
  const sanitizerName = [
    ...new Set(
      calls(builder)
        .filter(
          n =>
            ts.isIdentifier(n.expression) &&
            n.expression.text !== builder.name.text
        )
        .map(callName)
    ),
  ];
  assert.equal(sanitizerName.length, 1, "command sanitizer");
  const commandSanitizer = unique(
    descendants(ast, ts.isVariableDeclaration).filter(
      n => ts.isIdentifier(n.name) && n.name.text === sanitizerName[0]
    ),
    "command sanitizer declaration"
  );
  const rawName = callName(
    unique(
      calls(native).filter(
        n =>
          n.arguments.length === 1 &&
          ts.isStringLiteral(n.arguments[0]) &&
          n.arguments[0].text === "&>"
      ),
      "raw redirect marker"
    )
  );
  const raw = unique(
    functions.filter(n => n.name?.text === rawName),
    "raw-string helper"
  );
  const spawnFunction = unique(
    functions.filter(n => n.name?.text === spawnName),
    "native companion spawn helper"
  );
  const logNames = [
    ...new Set(
      [...calls(native), ...calls(spawnFunction)]
        .filter(
          n =>
            ts.isIdentifier(n.expression) &&
            ts.isAwaitExpression(n.parent) &&
            n.arguments.length === 1 &&
            ![rawName].includes(n.expression.text)
        )
        .map(callName)
    ),
  ];
  assert.equal(logNames.length, 1, "inert logger");
  const syncNames = [
    ...new Set(
      calls(wineExec)
        .filter(
          n =>
            ts.isIdentifier(n.expression) &&
            ![
              native.name.text,
              environment.name.text,
              taskPolicy.name.text,
            ].includes(n.expression.text)
        )
        .map(callName)
    ),
  ];
  assert.equal(syncNames.length, 2, "inert renderer synchronizers");
  const commands = [],
    syncs = [];
  const nativeContext = {
    [rootBindings.prefix]: "/default/prefix",
    [rootBindings.distro]: { attributes: { renderBackend: "dxmt" } },
    [rootBindings.wineRoot]: "/unchanged/per-game-wine",
    [rootBindings.renderer]: "dxmt",
    [rootBindings.d3dmetalPath]: undefined,
    [loader]: "/unchanged/per-game-wine/bin/wine",
    [variableForString("dxmt")]: "dxmt",
    [variableForString("d3dmetal")]: "d3dmetal",
    [logNames[0]]: async () => {},
    Neutralino: {
      os: {
        spawnProcess: async command => {
          commands.push(command);
          return { id: commands.length, pid: 200 + commands.length };
        },
      },
      events: {
        on: (name, handler) => {
          assert.equal(name, "spawnedProcess");
          Promise.resolve().then(() =>
            handler({
              detail: { id: commands.length, action: "exit", data: "0" },
            })
          );
        },
        off: () => {},
      },
    },
  };
  for (const name of syncNames)
    nativeContext[name] = async (...args) => {
      syncs.push({ name, args });
    };
  vm.createContext(nativeContext);
  vm.runInContext(
    "const " +
      text(commandSanitizer) +
      ";\n" +
      [environment, taskPolicy, wineExec, builder, raw, native, spawnFunction]
        .map(text)
        .join("\n"),
    nativeContext
  );
  const checks = [];
  for (const target of [60, 61, 90, 120, 121, 144, 150, 160, 2147483647]) {
    const output = launchOutputs.get(target);
    assert(output, "Launch output " + target);
    const before = commands.length;
    const result = await nativeContext[wineExec.name.text](
      "game.exe",
      [],
      output.game,
      "game.log"
    );
    assert.equal(result.exitCode, 0);
    await nativeContext[spawnFunction.name.text](
      ["bash", "./hoyoplay_genshin_fps_unlocker.sh"],
      output.companion
    );
    assert.equal(commands.length - before, 2);
    const [gameCommand, companionCommand] = commands.slice(before);
    assert(
      gameCommand.includes(
        "DXMT_CONFIG=d3d11.preferredMaxFrameRate=" +
          (target > 60 ? 0 : target) +
          "\\;"
      )
    );
    assert(
      companionCommand.includes(
        "DXMT_CONFIG=d3d11.preferredMaxFrameRate=" + target + "\\;"
      )
    );
    for (const command of [gameCommand, companionCommand]) {
      assert.equal(command.split("DXMT_CONFIG=").length, 2);
      assert(command.includes("other.setting=150\\;"));
      assert(command.includes("dxgi.customVendorId=1002\\;"));
      assert(
        command.includes("WINEPREFIX=/unchanged/prefix "),
        "Explicit prefix wins over per-game defaults"
      );
      assert(command.includes("UNRELATED=retained "));
    }
    assert(gameCommand.includes("/unchanged/per-game-wine/bin/wine game.exe"));
    assert(
      companionCommand.includes("bash ./hoyoplay_genshin_fps_unlocker.sh")
    );
    checks.push({ target, gameCommand, companionCommand, passed: true });
  }
  assert.equal(
    syncs.length,
    checks.length,
    "Each actual Wine exec2 retained renderer synchronization before native command"
  );
  assert(
    syncs.every(
      s => s.args.length === 1 && s.args[0] === "/unchanged/per-game-wine"
    )
  );
  return {
    allPassed: true,
    cases: checks.length,
    nativeCommandChecks: checks,
    rendererSyncCalls: syncs.length,
    limits: [
      "Actual packaged per-game Wine.exec2/default merge, command builder, Neutralino exec2 and companion spawn helpers executed with inert renderer sync, logger and Neutralino API/event callbacks.",
      "No operating-system processes or renderer files were touched; command strings were collected at the final Neutralino spawnProcess boundary.",
    ],
  };
}
(async () => {
  if (process.argv.includes("--assert-baseline-limitation")) {
    await assert.rejects(
      run({ target: 160 }),
      error =>
        error instanceof assert.AssertionError &&
        JSON.stringify(error.actual) === '["160"]' &&
        JSON.stringify(error.expected) === '["0"]'
    );
    console.log(
      "Confirmed regression sensitivity: accepted 417ed5c packaged target160 fails required game-DXMT0 assertion."
    );
    return;
  }
  for (const [raw, expected] of [
    ["", 120],
    ["0", 120],
    ["-1", 120],
    ["invalid", 120],
    ["NaN", 120],
    ["Infinity", 120],
    ["150.9", 150],
    ["60.9", 60],
    ["61.9", 61],
    ["160", 160],
  ])
    assert.equal(
      context[sanitize.name.text](raw),
      expected,
      "Retained sanitizer " + raw
    );
  for (const target of [
    1, 30, 59, 60, 61, 90, 120, 121, 144, 150, 160, 420, 2147483647,
  ])
    await run({ target });
  for (const target of [1, 30, 59, 60, 150, 160])
    await run({ target, enabled: false });
  for (const renderer of ["d3dmetal", "other"])
    for (const enabled of [false, true])
      for (const target of [60, 61, 120, 150, 160, 2147483647])
        await run({ target, enabled, renderer });
  for (const target of [
    "",
    "0",
    "-1",
    "invalid",
    "NaN",
    "Infinity",
    "150.9",
    "60.9",
    "61.9",
    "160",
  ])
    await run({ target });
  for (const input of [complexEnv, noRateEnv, absentEnv])
    for (const target of [60, 61, 120, 150, 160]) await run({ target, input });
  for (const target of [160, 60, 150, 90, 121, 160]) await run({ target });
  await run({
    target: 160,
    renderer: "other",
    input: Object.freeze({
      ...baseEnv,
      DXMT_CONFIG: "d3d11.preferredMaxFrameRate=150;other=on;",
    }),
  });
  await run({ target: 160, fail: true });
  await run({ target: 160, fail: true, renderer: "d3dmetal" });
  await run({ target: 160, endBeforeTimer: true });
  for (const gameId of ["unsupported-game"]) await run({ target: 160, gameId });
  const nativeForwarding = await verifyNativeForwarding();
  const report = {
    allPassed: true,
    nativeForwarding,
    cases,
    packagedJavaScript: inputFile,
    packagedJavaScriptSha256: crypto
      .createHash("sha256")
      .update(code)
      .digest("hex"),
    discoveredBindings: bindings,
    resourcePath: path.resolve(resourceFile),
    resourceSha256: sha256(bytes),
    archiveEntries: entries,
    events,
    nativeOperationsExecuted: 0,
    limits: [
      "Extracted packaged functions only, without application bootstrap; inert native and timer callbacks.",
      "Patch application, Wine waiting and reversion callbacks establish routing and finalization only; their implementation is separately source-compared.",
      "Positive finite targets beyond Int32.MaxValue remain accepted by existing launcher validation but are outside the original companion positional argument range.",
      "Automated configuration verification is not gameplay acceptance.",
    ],
  };
  const reportIndex = process.argv.indexOf("--report");
  if (reportIndex !== -1) {
    assert(process.argv[reportIndex + 1], "Report destination");
    fs.writeFileSync(
      process.argv[reportIndex + 1],
      JSON.stringify(report, null, 2) + "\n"
    );
  }
  console.log(
    "PASS " +
      cases +
      " actual packaged launch cases, including repeated calls on the same Wine object, final game/companion environments and numeric arguments, no native execution."
  );
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
