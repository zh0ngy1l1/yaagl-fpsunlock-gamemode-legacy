import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "path-browserify";
import ts from "typescript";
import type { Locale } from "@locale";

function sourceNode(relative: string, predicate: (node: ts.Node) => boolean) {
  const file = ts.createSourceFile(
    relative,
    readFileSync(relative, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX
  );
  const matches: ts.Node[] = [];
  function visit(node: ts.Node) {
    if (predicate(node)) matches.push(node);
    ts.forEachChild(node, visit);
  }
  visit(file);
  expect(matches).toHaveLength(1);
  return matches[0].getText(file);
}

const namedFunction = (relative: string, name: string) =>
  sourceNode(
    relative,
    node => ts.isFunctionDeclaration(node) && node.name?.text === name
  ).replace(/^export /, "");
const primary = namedFunction("src/launcher/hoyoplay.tsx", "onPrimaryAction");
const guardRegistration = sourceNode(
  "src/launcher/hoyoplay.tsx",
  node =>
    ts.isCallExpression(node) &&
    ts.isIdentifier(node.expression) &&
    node.expression.text === "addCloseGuard"
);
const wait = namedFunction(
  "src/launcher/hoyoplay-wine.ts",
  "waitUntilServerOff"
);
const gameProgram = namedFunction(
  "src/clients/mhy/hk4e/program-launch-game.ts",
  "launchGameProgram"
);

function evaluate(code: string, dependencies: Record<string, unknown>) {
  const js = ts.transpileModule(code, {
    compilerOptions: { target: ts.ScriptTarget.ES2020 },
  }).outputText;
  return new Function(...Object.keys(dependencies), js)(
    ...Object.values(dependencies)
  );
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>(yes => (resolve = yes));
  return { promise, resolve };
}
const settle = () => new Promise(resolve => setImmediate(resolve));
type Result = { pid: number; exitCode: number; stdOut: string; stdErr: string };
type Event = { detail: { id: number; action: string; data: string } };

beforeEach(() => {
  vi.resetModules();
});

async function harness() {
  // Actual primary action and close guard share one reservation, as in the UI.
  // The real queue, game generator, wait wrapper and close dispatcher run;
  // all process, filesystem, preference and patch effects remain inert.
  const neu = await import("../utils/neu");
  const { createHoyoplayTaskQueueState } = await import(
    "./hoyoplay-task-queue"
  );
  const events: string[] = [];
  const messages: string[] = [];
  const requests: Array<{
    command: string;
    resolve: (result: Result) => void;
  }> = [];
  const handlers = new Set<(event: Event) => void>();
  const feedback = deferred();
  const saves = deferred();
  const gameExit = deferred();
  const patchExit = deferred();
  const exit = vi.fn();
  const messageBox = vi.fn(async (): Promise<void> => undefined);
  const spawn = vi.fn(() => {
    throw new Error("Unexpected spawned process in inert integration test");
  });
  vi.stubGlobal("Neutralino", {
    app: { exit },
    debug: { log: async (message: string) => messages.push(message) },
    os: {
      showMessageBox: messageBox,
      spawnProcess: spawn,
      execCommand: async (command: string) =>
        new Promise<Result>(resolve => requests.push({ command, resolve })),
    },
    events: {
      on: async (_: string, handler: (event: Event) => void) =>
        handlers.add(handler),
      off: async (_: string, handler: (event: Event) => void) =>
        handlers.delete(handler),
    },
  });
  const waitUntilServerOff = evaluate(`${wait}; return waitUntilServerOff;`, {
    exec: neu.exec,
    join,
    dirname,
    loaderBin: "/mock selected Wine/bin/wine",
    getEnvironmentVariables: () => ({ WINEPREFIX: "/mock prefix" }),
  }) as () => Promise<Result>;
  const launchGameProgram = evaluate(
    `${gameProgram}; return launchGameProgram;`,
    {
      join,
      atob: (value: string) => Buffer.from(value, "base64").toString(),
      resolve: (value: string) => `/mock/${value}`,
      writeFile: vi.fn(),
      mkdirp: vi.fn(),
      removeFile: vi.fn(),
      log: neu.log,
      async *patchProgram() {
        events.push("patch applied");
      },
      async *patchRevertProgram() {
        events.push("patch cleanup started");
        await patchExit.promise;
        events.push("patch cleanup finished");
      },
    }
  );
  const wine = {
    setProps: vi.fn(),
    toWinePath: (value: string) => value,
    attributes: { renderBackend: "dxmt" },
    waitUntilServerOff,
    exec2: async () => {
      events.push("game started");
      await gameExit.promise;
      events.push("companion stop requested");
    },
  };
  const game = {
    id: "genshin",
    fpsTarget: () => "160",
    fpsEnabled: () => true,
    client: { installState: () => "INSTALLED", updateRequired: () => false },
  };
  const queue = createHoyoplayTaskQueueState({
    locale: { format: (key: string) => key } as unknown as Locale,
  });
  const saveWineSettings = vi.fn(() => saves.promise);
  const action = evaluate(
    `let primaryActionPending = false;
     ${guardRegistration}; ${primary}; return onPrimaryAction;`,
    {
      addCloseGuard: neu.addCloseGuard,
      programBusy: queue[2],
      statusText: queue[0],
      alert: neu.alert,
      locale: { get: (key: string) => key },
      isNormalCloseInProgress: neu.isNormalCloseInProgress,
      selectedGame: () => game,
      getFpsTargetError: () => undefined,
      saveWineSettings,
      saveRendererSettings: vi.fn(),
      saveFpsSettings: vi.fn(),
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
      launchProgram: () =>
        launchGameProgram({
          gameDir: "/mock game",
          gameExecutable: "game.exe",
          wine,
          config: {},
          server: { id: "hk4e_global" },
        }),
    }
  ) as () => Promise<void>;
  neu.addTerminationHook(async () => {
    events.push("helper terminated");
    return true;
  });
  return {
    action,
    close: neu.requestNormalClose,
    neu,
    events,
    messages,
    queue,
    saves,
    gameExit,
    patchExit,
    feedback,
    messageBox,
    saveWineSettings,
    spawn,
    exit,
    requests,
    emitUnrelatedExit: () => {
      for (const handler of handlers)
        handler({ detail: { id: 3, action: "exit", data: "143" } });
    },
    finishWait(index: number, exitCode = 0) {
      requests[index].resolve({
        pid: 1000 + index,
        exitCode,
        stdOut: "request-owned output",
        stdErr: exitCode ? "request-owned failure" : "",
      });
    },
  };
}

describe("combined launch ownership and request-owned Wine wait", () => {
  it.each([0, 143])(
    "holds launch and close admission after unrelated143 until its own wait%s and patch cleanup finish",
    async ownExit => {
      const h = await harness();
      const launch = h.action();
      h.saves.resolve();
      await settle();
      expect(h.requests).toHaveLength(1);
      h.finishWait(0);
      await settle();
      expect(h.events).toEqual(["patch applied", "game started"]);
      h.gameExit.resolve();
      await settle();
      expect(h.requests).toHaveLength(2);
      expect(h.requests[1].command).toBe(h.requests[0].command);
      h.emitUnrelatedExit();
      await settle();
      await h.action();
      await h.close();
      expect(h.queue[2]()).toBe(true);
      expect(h.saveWineSettings).toHaveBeenCalledTimes(1);
      expect(h.events).not.toContain("patch cleanup started");
      expect(h.events).not.toContain("helper terminated");
      expect(h.exit).not.toHaveBeenCalled();
      h.finishWait(1, ownExit);
      await settle();
      expect(h.events).toContain("patch cleanup started");
      expect(
        h.messages.some(message => message.includes("request-owned failure"))
      ).toBe(ownExit !== 0);
      await h.action();
      await h.close();
      expect(h.queue[2]()).toBe(true);
      expect(h.saveWineSettings).toHaveBeenCalledTimes(1);
      expect(h.exit).not.toHaveBeenCalled();
      h.patchExit.resolve();
      await launch;
      expect(h.queue[2]()).toBe(false);
      await h.close();
      expect(h.events.slice(-2)).toEqual([
        "patch cleanup finished",
        "helper terminated",
      ]);
      expect(h.exit).toHaveBeenCalledTimes(1);
      expect(h.spawn).not.toHaveBeenCalled();
    }
  );

  it("keeps new admission blocked when launch finishes before busy-close feedback returns", async () => {
    const h = await harness();
    const launch = h.action();
    h.messageBox.mockReturnValueOnce(h.feedback.promise);
    const closing = h.close();
    h.saves.resolve();
    await settle();
    h.finishWait(0);
    h.gameExit.resolve();
    await settle();
    h.finishWait(1);
    h.patchExit.resolve();
    await launch;
    expect(h.queue[2]()).toBe(false);
    await h.action();
    expect(h.saveWineSettings).toHaveBeenCalledTimes(1);
    expect(h.neu.isNormalCloseInProgress()).toBe(true);
    h.feedback.resolve();
    await closing;
    expect(h.neu.isNormalCloseInProgress()).toBe(false);
    expect(h.events).not.toContain("helper terminated");
    expect(h.exit).not.toHaveBeenCalled();
    const retry = h.action();
    await settle();
    h.finishWait(2);
    await settle();
    h.finishWait(3);
    await retry;
    expect(h.saveWineSettings).toHaveBeenCalledTimes(2);
  });
});
