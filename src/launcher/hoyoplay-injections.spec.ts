import { describe, expect, it, vi } from "vitest";
import type { CommonUpdateProgram } from "@common-update-ui";
import type { Wine } from "@wine";
import {
  withDxmtPreferredMaxFrameRate,
  withWineExec2Transform,
} from "./hoyoplay-injections";

vi.mock("@utils", () => ({}));

async function finish(program: CommonUpdateProgram) {
  while (!(await program.next()).done) {
    // Drain only mocked operations; no game, filesystem, or native calls.
  }
}

describe("DXMT process-local FPS configuration", () => {
  it.each([61, 90, 120, 121, 144, 150, 160, 420, 2147483647])(
    "retains target %i for the companion while final game configuration uses zero",
    async target => {
      const input = Object.freeze({
        KEEP: "unchanged",
        DXMT_CONFIG: "other=on;d3d11.preferredMaxFrameRate=60;last=off;",
      });
      const order: string[] = [];
      let companionEnv: Record<string, string> | undefined;
      let gameEnv: Record<string, string> | undefined;
      const exec2 = vi.fn(async (_command, _args, env) => {
        order.push("game");
        gameEnv = env;
      });
      const wine = { exec2 } as unknown as Wine;
      await finish(
        withWineExec2Transform(
          wine,
          env => withDxmtPreferredMaxFrameRate(env, target),
          async function* () {
            yield ["setStateText", "DOWNLOADING_ENVIRONMENT"];
            await wine.exec2("game", [], input);
          },
          {
            start(env) {
              order.push("schedule");
              companionEnv = env;
            },
            async stop() {
              order.push("stop");
            },
          },
          env => withDxmtPreferredMaxFrameRate(env, 0)
        )
      );
      expect(companionEnv).toEqual({
        KEEP: "unchanged",
        DXMT_CONFIG: `d3d11.preferredMaxFrameRate=${target};other=on;last=off;`,
      });
      expect(gameEnv).toEqual({
        KEEP: "unchanged",
        DXMT_CONFIG: "d3d11.preferredMaxFrameRate=0;other=on;last=off;",
      });
      expect(gameEnv).not.toBe(companionEnv);
      expect(input.DXMT_CONFIG).toBe(
        "other=on;d3d11.preferredMaxFrameRate=60;last=off;"
      );
      expect(order).toEqual(["schedule", "game", "stop"]);
    }
  );

  it("removes duplicate and spaced rate keys while retaining unrelated options", () => {
    const input = Object.freeze({
      DXMT_CONFIG:
        "alpha=1; d3d11.preferredMaxFrameRate = 60 ;other.d3d11.preferredMaxFrameRate=27;d3d11.preferredMaxFrameRate=-1;omega = 2 ;",
      DXMT_CONFIG_FILE: "/unchanged/dxmt.conf",
      KEEP: "retained",
    });
    const result = withDxmtPreferredMaxFrameRate(input, 160);
    expect(result).toEqual({
      ...input,
      DXMT_CONFIG:
        "d3d11.preferredMaxFrameRate=160;alpha=1;other.d3d11.preferredMaxFrameRate=27;omega = 2 ;",
    });
    expect(result).not.toBe(input);
  });

  it("does not interpret inherited rate150 when no game override is selected", async () => {
    const input = Object.freeze({
      DXMT_CONFIG: "d3d11.preferredMaxFrameRate=150;",
    });
    const exec2 = vi.fn(async () => undefined);
    const wine = { exec2 } as unknown as Wine;
    const start = vi.fn();
    await finish(
      withWineExec2Transform(
        wine,
        env => env,
        async function* () {
          await wine.exec2("game", [], input);
        },
        { start, stop: async () => undefined }
      )
    );
    expect(start).toHaveBeenCalledWith(input);
    expect(exec2).toHaveBeenCalledWith("game", [], input, undefined);
  });

  it("restores execution and stops the companion on game failure before a later launch", async () => {
    const failure = new Error("synthetic launch failure");
    const exec2 = vi
      .fn()
      .mockRejectedValueOnce(failure)
      .mockResolvedValue(undefined);
    const wine = { exec2 } as unknown as Wine;
    const stop = vi.fn(async () => undefined);
    const input = Object.freeze({ DXMT_CONFIG: "other=1;" });
    const first = withWineExec2Transform(
      wine,
      env => withDxmtPreferredMaxFrameRate(env, 160),
      async function* () {
        await wine.exec2("game", [], input);
      },
      { start: vi.fn(), stop },
      env => withDxmtPreferredMaxFrameRate(env, 0)
    );
    await expect(finish(first)).rejects.toBe(failure);
    expect(stop).toHaveBeenCalledTimes(1);
    await wine.exec2("game", [], input);
    expect(exec2.mock.calls[0][2]).toEqual({
      DXMT_CONFIG: "d3d11.preferredMaxFrameRate=0;other=1;",
    });
    expect(exec2.mock.calls[1][2]).toBe(input);
  });
});
