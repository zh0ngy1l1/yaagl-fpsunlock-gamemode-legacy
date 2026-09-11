import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import ts from "typescript";
import type { Locale } from "@locale";

function callback(relative: string, callName: string, firstArgument?: string) {
  const file = ts.createSourceFile(
    relative,
    readFileSync(relative, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX
  );
  const matches: ts.Node[] = [];
  function visit(node: ts.Node) {
    if (
      ts.isCallExpression(node) &&
      node.expression.getText(file) === callName &&
      (firstArgument === undefined ||
        (ts.isStringLiteral(node.arguments[0]) &&
          node.arguments[0].text === firstArgument))
    )
      matches.push(node.arguments[firstArgument === undefined ? 0 : 1]);
    ts.forEachChild(node, visit);
  }
  visit(file);
  expect(matches).toHaveLength(1);
  return ts.transpileModule(`const callback = ${matches[0].getText(file)}`, {
    compilerOptions: { target: ts.ScriptTarget.ES2020 },
  }).outputText;
}

const closeCallback = callback(
  "src/app.tsx",
  "Neutralino.events.on",
  "windowClose"
);
const ownershipCallback = callback(
  "src/launcher/hoyoplay.tsx",
  "addCloseGuard"
);
const primaryFile = ts.createSourceFile(
  "hoyoplay.tsx",
  readFileSync("src/launcher/hoyoplay.tsx", "utf8"),
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX
);
const primaryFunctions: ts.FunctionDeclaration[] = [];
const predownloadFunctions: ts.FunctionDeclaration[] = [];
const integrityCallbacks: ts.Node[] = [];
const initializationCallbacks: ts.Node[] = [];
function findPrimary(node: ts.Node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === "onPrimaryAction")
    primaryFunctions.push(node);
  if (ts.isFunctionDeclaration(node) && node.name?.text === "onPredownload")
    predownloadFunctions.push(node);
  if (
    ts.isJsxAttribute(node) &&
    node.name.text === "onClose" &&
    node.initializer &&
    ts.isJsxExpression(node.initializer) &&
    node.initializer.expression
      ?.getText(primaryFile)
      .includes("check-integrity")
  )
    integrityCallbacks.push(node.initializer.expression);
  if (
    ts.isCallExpression(node) &&
    node.expression.getText(primaryFile) === "games.forEach"
  )
    initializationCallbacks.push(node.arguments[0]);
  ts.forEachChild(node, findPrimary);
}
findPrimary(primaryFile);
expect(primaryFunctions).toHaveLength(1);
expect(predownloadFunctions).toHaveLength(1);
expect(integrityCallbacks).toHaveLength(1);
expect(initializationCallbacks).toHaveLength(1);
const primaryFunction = ts.transpileModule(
  primaryFunctions[0].getText(primaryFile),
  { compilerOptions: { target: ts.ScriptTarget.ES2020 } }
).outputText;

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>(yes => (resolve = yes));
  return { promise, resolve };
}

beforeEach(() => {
  vi.resetModules();
});

async function harness() {
  // Real close guards, termination dispatch and task queue; only helper/native
  // effects and client work are fixtures. No application bootstrap is executed.
  const neu = await import("../utils/neu");
  const { createHoyoplayTaskQueueState } = await import(
    "./hoyoplay-task-queue"
  );
  const events: string[] = [];
  const alert = vi.fn().mockResolvedValue(undefined);
  const exit = vi.fn();
  vi.stubGlobal("Neutralino", { app: { exit } });
  const queue = createHoyoplayTaskQueueState({
    locale: { format: (key: string) => key } as unknown as Locale,
  });
  const ownership = new Function(
    "programBusy",
    "statusText",
    "alert",
    "locale",
    `let primaryActionPending = false;
     ${ownershipCallback};
     return { guard: callback, setPending(value) { primaryActionPending = value; } };`
  )(queue[2], queue[0], alert, { get: (key: string) => key }) as {
    guard: () => Promise<boolean>;
    setPending(value: boolean): void;
  };
  const releaseGuard = neu.addCloseGuard(ownership.guard);
  const close = new Function(
    "requestNormalClose",
    `${closeCallback}; return callback;`
  )(neu.requestNormalClose) as () => Promise<void>;
  const game = {
    id: "genshin",
    fpsTarget: () => "160",
    fpsEnabled: () => true,
    client: { installState: () => "INSTALLED", updateRequired: () => false },
  };
  const saves = vi.fn();
  const actionDependencies = {
    programBusy: queue[2],
    isNormalCloseInProgress: neu.isNormalCloseInProgress,
    selectedGame: () => game,
    getFpsTargetError: () => undefined,
    saveWineSettings: saves,
    saveRendererSettings: saves,
    saveFpsSettings: saves,
    taskQueue: queue[3],
    namespacedProgram: (
      _a: unknown,
      _b: unknown,
      _g: unknown,
      _d: unknown,
      program: unknown
    ) => program,
    aria2: {},
    baseWine: {},
    d3dmetalPath: () => "",
    async *launchProgram() {
      events.push("new game");
    },
  };
  const action = new Function(
    ...Object.keys(actionDependencies),
    `let primaryActionPending = false; ${primaryFunction}; return onPrimaryAction;`
  )(...Object.values(actionDependencies)) as () => Promise<void>;
  function sourceAction(node: ts.Node, isDeclaration: boolean) {
    const dependencies = {
      ...actionDependencies,
      closeNativeSettings: vi.fn(),
      game: () => game,
    };
    const text = isDeclaration
      ? `${node.getText(primaryFile)}; const action = onPredownload;`
      : `const action = ${node.getText(primaryFile)};`;
    const code = ts.transpileModule(text, {
      compilerOptions: { target: ts.ScriptTarget.ES2020 },
    }).outputText;
    return new Function(
      ...Object.keys(dependencies),
      `${code}; return action;`
    )(...Object.values(dependencies)) as (argument?: unknown) => void;
  }
  const predownload = sourceAction(predownloadFunctions[0], true);
  const checkIntegrity = sourceAction(integrityCallbacks[0], false);
  const initialize = sourceAction(initializationCallbacks[0], false);
  neu.addTerminationHook(async () => {
    events.push("aria2 stop");
    return true;
  });
  neu.addTerminationHook(async () => {
    events.push("other helper stop");
    return true;
  });
  return {
    neu,
    events,
    alert,
    exit,
    ownership,
    queue,
    close,
    releaseGuard,
    action,
    saves,
    predownload,
    checkIntegrity,
    initialize: () => initialize(game),
  };
}

const settle = () => new Promise(resolve => setImmediate(resolve));

describe("HoYoPlay normal-close ownership", () => {
  it("vetoes before all helper termination/native exit until game, Wine wait and patch cleanup finish", async () => {
    const h = await harness();
    const game = deferred();
    const wine = deferred();
    const patch = deferred();
    h.ownership.setPending(true);
    await h.close();
    expect(h.alert).toHaveBeenLastCalledWith(
      "YAAGL",
      "CONFIGURING_ENVIRONMENT"
    );
    const completion = h.queue[3].next(async function* () {
      yield ["setStateText", "GAME_RUNNING"];
      await game.promise;
      h.events.push("companion stop");
      await wine.promise;
      yield ["setStateText", "REVERT_PATCHING"];
      await patch.promise;
      h.events.push("patch restored");
    });
    await settle();
    // Independently check queue ownership, including non-primary startup tasks.
    h.ownership.setPending(false);
    await h.close();
    expect(h.alert).toHaveBeenLastCalledWith("YAAGL", "GAME_RUNNING");
    expect(h.events).toEqual([]);
    game.resolve();
    await settle();
    await h.close();
    expect(h.events).toEqual(["companion stop"]);
    wine.resolve();
    await settle();
    await h.close();
    expect(h.alert).toHaveBeenLastCalledWith("YAAGL", "REVERT_PATCHING");
    expect(h.events).toEqual(["companion stop"]);
    expect(h.exit).not.toHaveBeenCalled();
    patch.resolve();
    await completion;
    h.ownership.setPending(false);
    await h.close();
    expect(h.events).toEqual([
      "companion stop",
      "patch restored",
      "other helper stop",
      "aria2 stop",
    ]);
    expect(h.exit).toHaveBeenCalledTimes(1);
    expect(h.exit).toHaveBeenCalledWith(0);
  });

  it("coalesces concurrent close events while feedback is pending without invoking any termination hook", async () => {
    const h = await harness();
    const feedback = deferred();
    h.alert.mockReturnValue(feedback.promise);
    h.ownership.setPending(true);
    const first = h.close();
    await h.close();
    expect(h.alert).toHaveBeenCalledTimes(1);
    expect(h.events).toEqual([]);
    expect(h.exit).not.toHaveBeenCalled();
    feedback.resolve();
    await first;
    h.ownership.setPending(false);
    await h.close();
    expect(h.exit).toHaveBeenCalledTimes(1);
  });

  it("coalesces close events during accepted shutdown before helper completion", async () => {
    const h = await harness();
    const helper = deferred();
    h.neu.addTerminationHook(async () => {
      h.events.push("pending helper stop");
      await helper.promise;
      return true;
    });
    const first = h.close();
    await settle();
    await h.action();
    expect(h.saves).not.toHaveBeenCalled();
    await h.close();
    expect(h.events).toEqual(["pending helper stop"]);
    expect(h.exit).not.toHaveBeenCalled();
    helper.resolve();
    await first;
    expect(h.events).toEqual([
      "pending helper stop",
      "other helper stop",
      "aria2 stop",
    ]);
    expect(h.exit).toHaveBeenCalledTimes(1);
  });

  it("blocks new actions throughout native exit and after its acknowledgement", async () => {
    const h = await harness();
    const nativeExit = deferred();
    h.exit.mockReturnValue(nativeExit.promise);
    let closeReturned = false;
    const closing = h.close().then(() => {
      closeReturned = true;
    });
    await settle();
    expect(h.exit).toHaveBeenCalledTimes(1);
    expect(closeReturned).toBe(false);
    await h.action();
    h.predownload();
    h.checkIntegrity("check-integrity");
    h.initialize();
    await h.close();
    expect(h.saves).not.toHaveBeenCalled();
    nativeExit.resolve();
    await closing;
    await h.action();
    expect(h.saves).not.toHaveBeenCalled();
    expect(h.neu.isNormalCloseInProgress()).toBe(true);
  });

  it("permits a legitimate action again after a rejected close", async () => {
    const h = await harness();
    h.ownership.setPending(true);
    await h.close();
    expect(h.neu.isNormalCloseInProgress()).toBe(false);
    h.ownership.setPending(false);
    await h.action();
    expect(h.saves).toHaveBeenCalledTimes(3);
    expect(h.events).toEqual(["new game"]);
    expect(h.exit).not.toHaveBeenCalled();
  });

  it("retains forced-shutdown behavior and supports unregistering a disposed owner", async () => {
    const h = await harness();
    h.ownership.setPending(true);
    expect(await h.neu.GLOBAL_onClose(true)).toBe(true);
    expect(h.alert).not.toHaveBeenCalled();
    expect(h.events).toHaveLength(2);
    h.releaseGuard();
    await h.close();
    expect(h.exit).toHaveBeenCalledTimes(1);
  });

  it("a feedback error still cannot terminate helpers or leave normal-close permanently locked", async () => {
    const h = await harness();
    h.ownership.setPending(true);
    h.alert.mockRejectedValueOnce(new Error("synthetic feedback failure"));
    await expect(h.close()).rejects.toThrow("synthetic feedback failure");
    expect(h.events).toEqual([]);
    expect(h.exit).not.toHaveBeenCalled();
    h.ownership.setPending(false);
    await h.close();
    expect(h.exit).toHaveBeenCalledTimes(1);
  });
});
