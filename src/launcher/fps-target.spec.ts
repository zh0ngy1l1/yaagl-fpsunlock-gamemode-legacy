import { beforeEach, describe, expect, it, vi } from "vitest";
import { getKeyOrDefault, setKey, spawn, writeFile } from "@utils";
import type { Wine } from "@wine";
import {
  FPS_TARGET_ERROR,
  getFpsTargetError,
  resolveFpsTarget,
} from "./fps-target";
import {
  getFpsConfig,
  setFpsConfig,
  setFpsUnlockEnabled,
  startGenshinFpsUnlockScript,
  withDxmtPreferredMaxFrameRate,
  withWineExec2Transform,
} from "./hoyoplay-injections";

vi.mock("@utils", () => ({
  getKeyOrDefault: vi.fn(),
  setKey: vi.fn(),
  writeFile: vi.fn(),
  spawn: vi.fn(),
  resolve: (path: string) => "/isolated/" + path.replace(/^\.\//, ""),
}));

const preferences = new Map<string, string>();

beforeEach(() => {
  vi.clearAllMocks();
  preferences.clear();
  vi.mocked(getKeyOrDefault).mockImplementation(
    async (key, fallback) => preferences.get(key) ?? fallback
  );
  vi.mocked(setKey).mockImplementation(async (key, value) => {
    if (value === null) preferences.delete(key);
    else preferences.set(key, value);
  });
  vi.mocked(spawn).mockResolvedValue({ id: 123, pid: 456 });
});

describe("canonical FPS target validation", () => {
  it.each([1, 30, 60, ...Array.from({ length: 300 }, (_, i) => i + 61)])(
    "resolves and serializes target %i without changing its argument or environment",
    async target => {
      await setFpsConfig("genshin", true, String(target));
      const stored = await getFpsConfig("genshin");
      expect(stored).toEqual({ enabled: true, target: String(target) });
      const resolved = resolveFpsTarget(stored.target);
      expect(resolved).toBe(target);

      const input = Object.freeze({
        KEEP: "original",
        DXMT_CONFIG: "other=1;d3d11.preferredMaxFrameRate=60;last=2;",
      });
      const exec2 = vi.fn(async () => undefined);
      const wine = { exec2, prefix: "/isolated/prefix" } as unknown as Wine;
      let companionEnv: Record<string, string> | undefined;
      const launch = withWineExec2Transform(
        wine,
        env => withDxmtPreferredMaxFrameRate(env, resolved),
        async function* () {
          await wine.exec2("mock-game", [], input);
        },
        {
          start(env) {
            companionEnv = env;
          },
          stop: async () => undefined,
        },
        resolved > 60 ? env => withDxmtPreferredMaxFrameRate(env, 0) : undefined
      );
      await launch.next();
      await startGenshinFpsUnlockScript(
        wine,
        resolved,
        "/isolated/per-game-wine/bin/wine",
        companionEnv
      );
      const companionConfig = `d3d11.preferredMaxFrameRate=${target};other=1;last=2;`;
      expect(companionEnv).toEqual({
        KEEP: "original",
        DXMT_CONFIG: companionConfig,
      });
      expect(exec2).toHaveBeenCalledWith(
        "mock-game",
        [],
        {
          KEEP: "original",
          DXMT_CONFIG:
            target > 60
              ? "d3d11.preferredMaxFrameRate=0;other=1;last=2;"
              : companionConfig,
        },
        undefined
      );
      const script = vi.mocked(writeFile).mock.calls[0][1];
      expect(script).toContain(`unlockfps.exe with target ${target}...`);
      expect(script).toMatch(new RegExp(`unlockfps\\.exe" ${target} &`));
      expect(spawn).toHaveBeenCalledWith(
        ["bash", "/isolated/hoyoplay_genshin_fps_unlocker.sh"],
        companionEnv
      );
      expect(input.DXMT_CONFIG).toBe(
        "other=1;d3d11.preferredMaxFrameRate=60;last=2;"
      );
    }
  );

  it.each([
    "361",
    "420",
    "2147483647",
    "150.5",
    "NaN",
    "Infinity",
    "",
    " ",
    "0",
    "-1",
  ])(
    "rejects invalid target %j before any preference or script write",
    async value => {
      preferences.set("hoyoplay_genshin_fps", "150");
      expect(getFpsTargetError(value)).toBe(FPS_TARGET_ERROR);
      expect(() => setFpsConfig("genshin", true, value)).toThrow(
        FPS_TARGET_ERROR
      );
      expect(setKey).not.toHaveBeenCalled();
      expect(preferences.get("hoyoplay_genshin_fps")).toBe("150");
      await expect(
        startGenshinFpsUnlockScript({} as Wine, Number(value))
      ).rejects.toThrow(FPS_TARGET_ERROR);
      expect(writeFile).not.toHaveBeenCalled();
      expect(spawn).not.toHaveBeenCalled();
    }
  );

  it.each(["361", "420", "150.5", "NaN", "Infinity", "", "0", "-1"])(
    "retains invalid legacy target %j visibly without silently defaulting or saving it",
    async value => {
      preferences.set("hoyoplay_genshin_fps", value);
      const config = await getFpsConfig("genshin");
      expect(config.target).toBe(value);
      expect(() => resolveFpsTarget(config.target)).toThrow(FPS_TARGET_ERROR);
      expect(setKey).not.toHaveBeenCalled();
      await setFpsUnlockEnabled("genshin", false);
      expect(preferences.get("hoyoplay_genshin_fps")).toBe(value);
      expect(await getFpsConfig("genshin")).toEqual({
        enabled: false,
        target: value,
      });
      expect(setKey).toHaveBeenCalledTimes(1);
      expect(setKey).toHaveBeenCalledWith(
        "hoyoplay_genshin_fps_enabled",
        "false"
      );
    }
  );

  it("defaults only a missing target to120 without writing it", async () => {
    expect(await getFpsConfig("genshin")).toEqual({
      enabled: true,
      target: "120",
    });
    expect(setKey).not.toHaveBeenCalled();
  });

  it("retains valid saved150 and its disabled flag without writes", async () => {
    preferences.set("hoyoplay_genshin_fps", "150");
    preferences.set("hoyoplay_genshin_fps_enabled", "false");
    expect(await getFpsConfig("genshin")).toEqual({
      enabled: false,
      target: "150",
    });
    expect(setKey).not.toHaveBeenCalled();
  });
});
