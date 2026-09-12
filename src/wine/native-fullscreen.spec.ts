import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { exec, getKeyOrDefault, setKey } from "@utils";
import {
  readNativeFullscreen,
  saveNativeFullscreen,
} from "../config/native-fullscreen-setting";
import { SETTING_DEFAULTS } from "../config/defaults";
import {
  ensureNativeFullscreenEngine,
  nativeFullscreenEnvironment,
  NATIVE_FULLSCREEN_DISTRO,
  prepareNativeFullscreen,
} from "./native-fullscreen";
import type { Wine } from "./wine";

vi.mock("@utils", () => ({
  exec: vi.fn(),
  getKeyOrDefault: vi.fn(),
  setKey: vi.fn(),
  resolve: (s: string) => "/app/" + s,
}));
const preferences = new Map<string, string>();
beforeEach(() => {
  vi.clearAllMocks();
  preferences.clear();
  vi.mocked(getKeyOrDefault).mockImplementation(
    async (key, fallback) => preferences.get(key) ?? fallback
  );
  vi.mocked(setKey).mockImplementation(async (key, value) => {
    if (value !== null) preferences.set(key, value);
  });
});

describe("Native Fullscreen setting and launch policy", () => {
  it("defaults Off without writing; persists both states independently of Metal HUD", async () => {
    expect(SETTING_DEFAULTS.config_nativeFullscreen).toBe(false);
    expect(await readNativeFullscreen()).toBe(false);
    expect(setKey).not.toHaveBeenCalled();
    preferences.set("config_metalHud", "false");
    await saveNativeFullscreen(true);
    expect(await readNativeFullscreen()).toBe(true);
    await saveNativeFullscreen(false);
    expect(await readNativeFullscreen()).toBe(false);
    expect(preferences.get("config_metalHud")).toBe("false");
    expect(
      vi
        .mocked(setKey)
        .mock.calls.every(([key]) => key === "config_nativeFullscreen")
    ).toBe(true);
  });
  it("places the row directly before Metal HUD and gates the control by selected distro", () => {
    const ui = readFileSync("src/config/index.tsx", "utf8");
    expect(ui).toMatch(/<NF\s*\/>\s*<MH\s*\/>/);
    const row = readFileSync("src/config/native-fullscreen.tsx", "utf8");
    expect(row).toContain("disabled={!supported() || saving()}");
    expect(row).toContain("get: () => supported() && value()");
    expect(row).toContain("Applies on next launch.");
    expect(row).toContain("Requires Wine 11.0 DXMT (signed, with patches).");
    const storage = readFileSync("src/utils/neu.ts", "utf8");
    expect(storage).toContain('key == "config_nativeFullscreen" ||');
  });
  it.each([false, true, false, true])(
    "writes both global and app opt-in for requested %s without touching modifiers",
    async enabled => {
      const wine = {
        attributes: { distributionId: NATIVE_FULLSCREEN_DISTRO },
        exec: vi.fn(),
        waitUntilServerOff: vi.fn(),
      } as unknown as Wine;
      const env = await prepareNativeFullscreen(
        wine,
        enabled,
        "GenshinImpact.exe"
      );
      expect(env).toEqual({ YAAGL_NATIVE_FULLSCREEN: enabled ? "1" : "0" });
      expect(wine.exec).toHaveBeenCalledTimes(2);
      for (const key of [
        "HKEY_CURRENT_USER\\Software\\Wine\\Mac Driver",
        "HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\GenshinImpact.exe\\Mac Driver",
      ]) {
        expect(wine.exec).toHaveBeenCalledWith(
          "reg",
          [
            "add",
            key,
            "/v",
            "AllowFixedSizeFullscreen",
            "/t",
            "REG_SZ",
            "/d",
            enabled ? "Y" : "N",
            "/f",
          ],
          { YAAGL_NATIVE_FULLSCREEN: "0" },
          "/dev/null"
        );
      }
      expect(wine.waitUntilServerOff).toHaveBeenCalledTimes(1);
    }
  );
  it.each(["9.9-dxmt", "__shared__", "11.0-dxmt-signed", "custom"])(
    "never enables or installs support for %s",
    async distributionId => {
      const wine = {
        attributes: { distributionId },
        exec: vi.fn(),
        waitUntilServerOff: vi.fn(),
      } as unknown as Wine;
      expect(await prepareNativeFullscreen(wine, true, "game.exe")).toEqual({
        YAAGL_NATIVE_FULLSCREEN: "0",
      });
      await ensureNativeFullscreenEngine("/wine", distributionId);
      expect(wine.exec).not.toHaveBeenCalled();
      expect(exec).not.toHaveBeenCalled();
      expect(
        nativeFullscreenEnvironment(distributionId, {
          YAAGL_NATIVE_FULLSCREEN: "1",
          KEPT: "literal",
        })
      ).toEqual({ YAAGL_NATIVE_FULLSCREEN: "0", KEPT: "literal" });
    }
  );
  it("preserves other environment values including independent Metal HUD", () => {
    for (const hud of ["", "1"])
      for (const flag of ["0", "1"]) {
        const env = {
          YAAGL_NATIVE_FULLSCREEN: flag,
          MTL_HUD_ENABLED: hud,
          KEPT: "a $literal; 日本語",
          WINEPREFIX: "/prefix with spaces",
        };
        expect(
          nativeFullscreenEnvironment(NATIVE_FULLSCREEN_DISTRO, env)
        ).toEqual(env);
      }
    expect(nativeFullscreenEnvironment(NATIVE_FULLSCREEN_DISTRO)).toEqual({
      YAAGL_NATIVE_FULLSCREEN: "0",
    });
  });
  it("propagates a registry failure instead of starting with stale state", async () => {
    const wine = {
      attributes: { distributionId: NATIVE_FULLSCREEN_DISTRO },
      exec: vi.fn().mockRejectedValue(new Error("registry failed")),
      waitUntilServerOff: vi.fn(),
    } as unknown as Wine;
    await expect(
      prepareNativeFullscreen(wine, false, "game.exe")
    ).rejects.toThrow("registry failed");
  });
});
