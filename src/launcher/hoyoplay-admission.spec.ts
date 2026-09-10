import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import ts from "typescript";
import { createHoyoplayTaskQueueState } from "./hoyoplay-task-queue";
import type { Locale } from "@locale";

vi.mock("@utils", () => ({ alert: vi.fn(), humanDuration: vi.fn() }));

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

const source = ts.createSourceFile(
  "hoyoplay.tsx",
  readFileSync("src/launcher/hoyoplay.tsx", "utf8"),
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX
);
const found: ts.FunctionDeclaration[] = [];
function visit(node: ts.Node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === "onPrimaryAction")
    found.push(node);
  ts.forEachChild(node, visit);
}
visit(source);
expect(found).toHaveLength(1);

// Run the actual primary-action body against the actual async task queue.
// All settings, client operations and namespace entry are inert fixtures.
function harness(legacyAdmission = false) {
  const events: string[] = [];
  const saving = deferred();
  const gameExit = deferred();
  const wineExit = deferred();
  const patchExit = deferred();
  let failLaunch = false;
  let installed = true;
  let update = false;
  let invalid = false;
  const game = {
    id: "genshin",
    fpsTarget: () => "160",
    fpsEnabled: () => true,
    client: {
      installState: () => (installed ? "INSTALLED" : "ABSENT"),
      updateRequired: () => update,
      updateSizeBytes: () => 1,
      async *update() {
        events.push("update");
      },
      async *install() {
        events.push("install");
      },
    },
  };
  const queue = createHoyoplayTaskQueueState({
    locale: { format: () => "status" } as unknown as Locale,
  });
  const saveWineSettings = vi.fn(() => saving.promise);
  const dependencies = {
    programBusy: queue[2],
    isNormalCloseInProgress: vi.fn().mockReturnValue(false),
    selectedGame: () => game,
    getFpsTargetError: () => (invalid ? "invalid" : undefined),
    openNativeSettings: vi.fn(),
    saveWineSettings,
    saveRendererSettings: vi.fn(),
    saveFpsSettings: vi.fn(),
    setFpsUnlockEnabled: vi.fn(),
    setPendingSizeBytes: queue[6],
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
      events.push("game");
      try {
        await gameExit.promise;
        if (failLaunch) throw new Error("synthetic game failure");
      } finally {
        events.push("companion stop");
        await wineExit.promise;
        events.push("wine stopped");
        await patchExit.promise;
        events.push("patch restored");
      }
    },
    selectPath: vi.fn().mockResolvedValue(undefined),
  };
  let body = found[0].getText(source);
  if (legacyAdmission) {
    // Removing just the new reservation reproduces the original asynchronous
    // admission gap, even if taskQueue.next is now awaited by its caller.
    body = body.replace(
      "programBusy() || primaryActionPending",
      "programBusy()"
    );
  }
  const js = ts.transpileModule(body, {
    compilerOptions: { target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const action = new Function(
    ...Object.keys(dependencies),
    `let primaryActionPending = false; ${js}; return onPrimaryAction;`
  )(...Object.values(dependencies)) as () => Promise<void>;
  return {
    action,
    events,
    saving,
    gameExit,
    wineExit,
    patchExit,
    dependencies,
    fail: () => (failLaunch = true),
    selectInstall: () => (installed = false),
    selectUpdate: () => (update = true),
    setInvalid: (value: boolean) => (invalid = value),
  };
}

const settle = () => new Promise(resolve => setImmediate(resolve));
beforeEach(() => {
  vi.clearAllMocks();
});

describe("Genshin primary-action admission", () => {
  it("reproduces two serial launches when overlapping settings saves have only the old busy guard", async () => {
    const h = harness(true);
    const first = h.action();
    const second = h.action();
    expect(h.dependencies.saveWineSettings).toHaveBeenCalledTimes(2);
    h.saving.resolve();
    await settle();
    expect(h.events).toEqual(["game"]);
    h.gameExit.resolve();
    h.wineExit.resolve();
    h.patchExit.resolve();
    await Promise.all([first, second]);
    expect(h.events).toEqual([
      "game",
      "companion stop",
      "wine stopped",
      "patch restored",
      "game",
      "companion stop",
      "wine stopped",
      "patch restored",
    ]);
  });

  it("admits once before saving, then holds ownership through game, companion, Wine and patch cleanup", async () => {
    const h = harness();
    let finished = false;
    const first = h.action().then(() => (finished = true));
    await h.action();
    expect(h.dependencies.saveWineSettings).toHaveBeenCalledTimes(1);
    h.saving.resolve();
    await settle();
    await h.action();
    h.gameExit.resolve();
    await settle();
    expect(h.events).toEqual(["game", "companion stop"]);
    expect(finished).toBe(false);
    await h.action();
    h.wineExit.resolve();
    await settle();
    expect(h.events).toEqual(["game", "companion stop", "wine stopped"]);
    expect(finished).toBe(false);
    await h.action();
    h.patchExit.resolve();
    await first;
    expect(h.events).toEqual([
      "game",
      "companion stop",
      "wine stopped",
      "patch restored",
    ]);
    expect(h.dependencies.saveWineSettings).toHaveBeenCalledTimes(1);
    await h.action();
    expect(h.events.filter(event => event === "game")).toHaveLength(2);
  });

  it("releases admission after a settings error without launching or rewriting the selection", async () => {
    const h = harness();
    h.dependencies.saveWineSettings.mockRejectedValueOnce(
      new Error("save failed")
    );
    await expect(h.action()).rejects.toThrow("save failed");
    expect(h.events).toEqual([]);
    const retry = h.action();
    h.saving.resolve();
    h.gameExit.resolve();
    h.wineExit.resolve();
    h.patchExit.resolve();
    await retry;
    expect(h.events.filter(event => event === "game")).toHaveLength(1);
  });

  it("allows a later action after a failed task has completed cleanup", async () => {
    const h = harness();
    h.fail();
    h.saving.resolve();
    h.gameExit.resolve();
    h.wineExit.resolve();
    h.patchExit.resolve();
    await h.action();
    await h.action();
    expect(h.events).toEqual([
      "game",
      "companion stop",
      "wine stopped",
      "patch restored",
      "game",
      "companion stop",
      "wine stopped",
      "patch restored",
    ]);
  });

  it("releases admission after invalid-target navigation and cancelled installation", async () => {
    const h = harness();
    h.setInvalid(true);
    await h.action();
    expect(h.dependencies.openNativeSettings).toHaveBeenCalledTimes(1);
    expect(h.dependencies.saveWineSettings).not.toHaveBeenCalled();
    h.setInvalid(false);
    h.selectInstall();
    h.saving.resolve();
    await h.action();
    await h.action();
    expect(h.dependencies.selectPath).toHaveBeenCalledTimes(2);
    expect(h.events).toEqual([]);
  });

  it("retains update dispatch and permits another legitimate action after completion", async () => {
    const h = harness();
    h.selectUpdate();
    h.saving.resolve();
    await h.action();
    await h.action();
    expect(h.events).toEqual(["update", "update"]);
  });
});
