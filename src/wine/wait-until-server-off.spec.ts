import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { dirname, join } from "path-browserify";
import ts from "typescript";
import { exec, exec2 } from "../utils/neu";
import { build } from "../utils/command-builder";

type Child = { id: number; pid: number; name: string };
type Result = { pid: number; exitCode: number; stdOut: string; stdErr: string };
type Event = { detail: { id: number; action: string; data: string } };

const handlers = new Set<(event: Event) => void>();
const children = new Map<number, Child>();
let nextPid: number;
let requests: {
  command: string;
  child: Child;
  resolve: (result: Result) => void;
}[];
let spawned: Child[];

function allocate(name: string) {
  // Exact Native4.11 allocator confirmed in installed binary: map.size().
  const child = { id: children.size, pid: nextPid++, name };
  children.set(child.id, child);
  return child;
}

function finishSpawned(child: Child, exitCode: number) {
  for (const handler of handlers) {
    handler({
      detail: { id: child.id, action: "exit", data: String(exitCode) },
    });
  }
  // Native exit thread dispatches the cached ID and then erases that map key,
  // even if a later allocation has overwritten the entry with another child.
  children.delete(child.id);
}

function waitingEnvironment() {
  return {
    WINEPREFIX: "/mock prefix",
    WINEDEBUG: "fixme-all,err-unwind,+timestamp",
  };
}

function sourceWait(relative: string, old = false) {
  const text = readFileSync(resolve(relative), "utf8");
  const source = ts.createSourceFile(
    relative,
    text,
    ts.ScriptTarget.Latest,
    true
  );
  const found: ts.FunctionDeclaration[] = [];
  function visit(node: ts.Node) {
    if (
      ts.isFunctionDeclaration(node) &&
      node.name?.text === "waitUntilServerOff"
    )
      found.push(node);
    ts.forEachChild(node, visit);
  }
  visit(source);
  expect(found).toHaveLength(1);
  let body = found[0].getText(source);
  if (old)
    body = body
      .replace("return await unixExec(", "return await unixExec2(")
      .replace("return await exec(", "return await exec2(");
  const code = ts.transpileModule(body, {
    compilerOptions: { target: ts.ScriptTarget.ES2020 },
  }).outputText;
  return new Function(
    "exec",
    "exec2",
    "unixExec",
    "unixExec2",
    "join",
    "dirname",
    "loaderBin",
    "getEnvironmentVariables",
    code + ";return waitUntilServerOff;"
  )(
    exec,
    exec2,
    exec,
    exec2,
    join,
    dirname,
    "/mock per-game Wine/bin/wine",
    waitingEnvironment
  ) as () => Promise<Result>;
}

beforeEach(() => {
  handlers.clear();
  children.clear();
  nextPid = 1000;
  requests = [];
  spawned = [];
  vi.stubGlobal("Neutralino", {
    debug: { log: async () => undefined },
    events: {
      on: async (_: string, handler: (event: Event) => void) =>
        handlers.add(handler),
      off: async (_: string, handler: (event: Event) => void) =>
        handlers.delete(handler),
    },
    os: {
      spawnProcess: async (command: string) => {
        const child = allocate(command);
        spawned.push(child);
        return child;
      },
      execCommand: async (command: string) =>
        new Promise<Result>(resolve => {
          // Request-scoped native execCommand children do not enter the shared
          // spawned-process map or dispatch its virtual-ID events.
          const child = { id: -1, pid: nextPid++, name: command };
          requests.push({ command, child, resolve });
        }),
    },
  });
});

function leaveCompanionAfterGame() {
  allocate("aria2");
  allocate("sophon");
  const game = allocate("game");
  const companion = allocate("companion");
  finishSpawned(game, 0);
  expect(children.size).toBe(companion.id);
  return companion;
}

const settle = () => new Promise(resolve => setImmediate(resolve));

describe.each(["src/wine/wine.ts", "src/launcher/hoyoplay-wine.ts"])(
  "Wine wait request ownership: %s",
  source => {
    it("reproduces the old wrong143 result from the stopped companion virtual-ID collision", async () => {
      const companion = leaveCompanionAfterGame();
      const result = sourceWait(source, true)();
      const rejection = expect(result).rejects.toThrow("non-zero code (143)");
      await settle();
      expect(spawned).toHaveLength(1);
      expect(spawned[0].id).toBe(companion.id);
      expect(spawned[0].pid).not.toBe(companion.pid);
      finishSpawned(companion, 143);
      await rejection;
      expect(handlers.size).toBe(0);
      // No actual Wine-wait child completion was emitted in this reproduction.
    });

    it("waits for its own exit after a stale companion143 without changing command or environment", async () => {
      const companion = leaveCompanionAfterGame();
      let settled = false;
      const result = sourceWait(source)().finally(() => {
        settled = true;
      });
      await settle();
      expect(requests).toHaveLength(1);
      expect(requests[0].command).toBe(
        build(
          ["/mock per-game Wine/bin/wineserver", "-w"],
          waitingEnvironment()
        )
      );
      expect(spawned).toHaveLength(0);
      expect(handlers.size).toBe(0);
      finishSpawned(companion, 143);
      await settle();
      expect(settled).toBe(false);
      const success = {
        pid: requests[0].child.pid,
        exitCode: 0,
        stdOut: "own stdout",
        stdErr: "own stderr",
      };
      requests[0].resolve(success);
      expect(await result).toEqual(success);
    });

    it("continues to reject a real request-scoped143 and retains its diagnostic output", async () => {
      const result = sourceWait(source)();
      const rejection = expect(result).rejects.toThrow("own failure");
      await settle();
      requests[0].resolve({
        pid: requests[0].child.pid,
        exitCode: 143,
        stdOut: "",
        stdErr: "own failure",
      });
      await rejection;
      expect(spawned).toHaveLength(0);
    });

    it("does not cross-resolve overlapping waits or advance cleanup before the real result", async () => {
      const order: string[] = [];
      const first = sourceWait(source)().then(() =>
        order.push("first cleanup")
      );
      const second = sourceWait(source)().then(() =>
        order.push("second cleanup")
      );
      await settle();
      expect(requests).toHaveLength(2);
      expect(order).toEqual([]);
      const exit = (i: number) =>
        requests[i].resolve({
          pid: requests[i].child.pid,
          exitCode: 0,
          stdOut: "",
          stdErr: "",
        });
      exit(1);
      await second;
      expect(order).toEqual(["second cleanup"]);
      exit(0);
      await first;
      expect(order).toEqual(["second cleanup", "first cleanup"]);
    });
  }
);
