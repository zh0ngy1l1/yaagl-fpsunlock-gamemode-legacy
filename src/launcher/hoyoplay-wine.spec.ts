import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import ts from "typescript";
import {
  ensureHoyoplayGameWine,
  getHoyoplayGameWineTag,
  getHoyoplayWineBin,
  getHoyoplayWineOptions,
  getHoyoplayWineInstallationDistribution,
  prepareFreshHoyoplayWineSelection,
  setHoyoplayGameWineTag,
  SHARED_WINE_TAG,
} from "./hoyoplay-wine";
import { DEFAULT_WINE_DISTRIBUTION } from "../config/defaults";
import { exec, getKey, getKeyOrDefault, setKey, stats } from "@utils";
import type { Aria2 } from "@aria2";
import type { Wine } from "@wine";

vi.mock("@utils", () => ({
  getKey: vi.fn(),
  getKeyOrDefault: vi.fn(),
  setKey: vi.fn(),
  stats: vi.fn(),
  resolve: (path: string) => "/isolated/" + path.replace(/^\.\//, ""),
  exec: vi.fn(),
  exec2: vi.fn(),
}));
vi.mock("@wine", () => ({
  getWineDistributions: async () => [
    {
      id: "11.0-dxmt-signed-with-patches",
      displayName: "Wine 11.0 DXMT (signed, with patches)",
      remoteUrl: "mock://wine-11.0.tar.xz",
      attributes: { renderBackend: "dxmt", winePath: "wine" },
    },
    {
      id: "9.9-dxmt",
      displayName: "Wine 9.9 DXMT",
      remoteUrl: "mock://wine-9.9.tar.gz",
      attributes: { renderBackend: "dxmt" },
    },
  ],
}));
vi.mock("../wine/cert", () => ({ addCertsToWine: vi.fn() }));
vi.mock("../downloadable-resource", () => ({ DXMT_FILES: [] }));

const preferences = new Map<string, string>();
const readDirectory = vi.fn();
const baseWine = { prefix: "/unchanged/prefix" } as Awaited<Wine>;
const aria2 = {} as Aria2;

beforeEach(() => {
  vi.clearAllMocks();
  preferences.clear();
  vi.stubGlobal("Neutralino", { filesystem: { readDirectory } });
  readDirectory.mockResolvedValue([]);
  vi.mocked(getKey).mockImplementation(async key => {
    const value = preferences.get(key);
    if (value === undefined) {
      throw Object.assign(new Error("Absent test key"), {
        code: "NE_ST_NOSTKEX",
      });
    }
    return value;
  });
  vi.mocked(getKeyOrDefault).mockImplementation(
    async (key, fallback) => preferences.get(key) ?? fallback
  );
  vi.mocked(setKey).mockImplementation(async (key, value) => {
    if (value === null) preferences.delete(key);
    else preferences.set(key, value);
  });
  vi.mocked(stats).mockRejectedValue(new Error("Absent mock Wine"));
});

describe("Genshin Wine fallback and inherited runtime compatibility", () => {
  it("fresh and partial settings resolve the default without writes", async () => {
    preferences.set("config_metalHud", "false");
    expect(await getHoyoplayGameWineTag("genshin")).toBe(
      DEFAULT_WINE_DISTRIBUTION
    );
    expect(setKey).not.toHaveBeenCalled();
  });

  it.each(["9.9-dxmt", "__shared__", "unlisted-custom-build", ""])(
    "preserves explicit per-game tag %j even with no global Wine metadata",
    async tag => {
      preferences.set("hoyoplay_genshin_wine_tag", tag);
      expect(await getHoyoplayGameWineTag("genshin")).toBe(tag);
      await prepareFreshHoyoplayWineSelection("genshin");
      expect(setKey).not.toHaveBeenCalled();
      expect(readDirectory).not.toHaveBeenCalled();
    }
  );

  it.each([
    ["wine_tag", "9.9-dxmt"],
    ["wine_tag", "unlisted-custom-build"],
    ["wine_state", "ready"],
    ["wine_state", "update"],
    ["wine_tag", ""],
  ])("keeps inherited root for existing %s=%j", async (key, value) => {
    preferences.set(key, value);
    expect(await getHoyoplayGameWineTag("genshin")).toBe(SHARED_WINE_TAG);
    await prepareFreshHoyoplayWineSelection("genshin");
    expect(setKey).not.toHaveBeenCalled();
    const result = await ensureHoyoplayGameWine({
      aria2,
      baseWine,
      gameId: "genshin",
      wineTag: SHARED_WINE_TAG,
    }).next();
    expect(result).toEqual({ done: true, value: baseWine });
    expect(await getHoyoplayWineBin("genshin", SHARED_WINE_TAG)).toBe(
      "/isolated/wine/bin/wine"
    );
    expect(stats).not.toHaveBeenCalled();
    expect(exec).not.toHaveBeenCalled();
  });

  it.each(["wine", "wineprefix"])(
    "preserves missing-metadata installation with %s entry (including a broken link)",
    async entry => {
      readDirectory.mockResolvedValue([{ entry, type: "DIRECTORY" }]);
      expect(await getHoyoplayGameWineTag("genshin")).toBe(SHARED_WINE_TAG);
      await prepareFreshHoyoplayWineSelection("genshin");
      expect(setKey).not.toHaveBeenCalled();
    }
  );

  it("does not infer freshness from an unreadable application directory", async () => {
    readDirectory.mockRejectedValue(new Error("Access denied"));
    expect(await getHoyoplayGameWineTag("genshin")).toBe(SHARED_WINE_TAG);
    await prepareFreshHoyoplayWineSelection("genshin");
    expect(setKey).not.toHaveBeenCalled();
  });

  it("reserves fresh default once before the installer writes shared Wine metadata", async () => {
    await prepareFreshHoyoplayWineSelection("genshin");
    preferences.set("wine_tag", "9.9-dxmt");
    preferences.set("wine_state", "ready");
    readDirectory.mockResolvedValue([{ entry: "wine", type: "DIRECTORY" }]);
    await prepareFreshHoyoplayWineSelection("genshin");
    expect(await getHoyoplayGameWineTag("genshin")).toBe(
      DEFAULT_WINE_DISTRIBUTION
    );
    expect(setKey).toHaveBeenCalledTimes(1);
    expect(setKey).toHaveBeenCalledWith(
      "hoyoplay_genshin_wine_tag",
      DEFAULT_WINE_DISTRIBUTION
    );
  });

  it("retains one-time reservation across an interrupted initial install", async () => {
    await prepareFreshHoyoplayWineSelection("genshin");
    readDirectory.mockResolvedValue([{ entry: "wine", type: "DIRECTORY" }]);
    await prepareFreshHoyoplayWineSelection("genshin");
    expect(await getHoyoplayGameWineTag("genshin")).toBe(
      DEFAULT_WINE_DISTRIBUTION
    );
    expect(setKey).toHaveBeenCalledTimes(1);
  });

  it("propagates reservation storage failure instead of continuing initialization", async () => {
    vi.mocked(setKey).mockRejectedValueOnce(new Error("Storage write failed"));
    await expect(prepareFreshHoyoplayWineSelection("genshin")).rejects.toThrow(
      "Storage write failed"
    );
    expect(preferences.has("hoyoplay_genshin_wine_tag")).toBe(false);
  });

  it("keeps exact legacy missing/explicit representation on Save", async () => {
    await setHoyoplayGameWineTag("genshin", SHARED_WINE_TAG);
    expect(setKey).not.toHaveBeenCalled();
    preferences.set("hoyoplay_genshin_wine_tag", SHARED_WINE_TAG);
    await setHoyoplayGameWineTag("genshin", SHARED_WINE_TAG);
    expect(setKey).not.toHaveBeenCalled();
    await setHoyoplayGameWineTag("genshin", "9.9-dxmt");
    expect(preferences.get("hoyoplay_genshin_wine_tag")).toBe("9.9-dxmt");
  });

  it("names legacy runtime accurately without an available generic shared choice", async () => {
    preferences.set("wine_tag", "9.9-dxmt");
    const options = await getHoyoplayWineOptions(SHARED_WINE_TAG);
    expect(options[0]).toMatchObject({
      tag: SHARED_WINE_TAG,
      displayName: "Wine 9.9 DXMT (existing runtime)",
      disabled: true,
    });
    expect(
      (await getHoyoplayWineOptions(DEFAULT_WINE_DISTRIBUTION)).some(
        option => option.tag === SHARED_WINE_TAG
      )
    ).toBe(false);
  });

  it("does not label unidentified inherited Wine as the default distribution", async () => {
    const [missing] = await getHoyoplayWineOptions(SHARED_WINE_TAG);
    expect(missing.displayName).toBe(
      "Existing runtime (distribution not identified)"
    );
    preferences.set("wine_tag", "custom-legacy");
    const [unknown] = await getHoyoplayWineOptions(SHARED_WINE_TAG);
    expect(unknown.displayName).toBe(
      "custom-legacy (existing runtime; distribution not identified)"
    );
  });

  it("preserves raw unknown per-game tags for explicit existing selection", async () => {
    const options = await getHoyoplayWineOptions("custom-per-game");
    expect(options.at(-1)).toMatchObject({
      tag: "custom-per-game",
      displayName: "custom-per-game",
    });
    await expect(
      getHoyoplayWineBin("genshin", "custom-per-game")
    ).rejects.toThrow("Unknown Wine distribution: custom-per-game");
  });

  it("retains original prefix and per-game loader path for an installed concrete selection", async () => {
    preferences.set("wine_netbiosname", "DESKTOP-ISOLATE");
    vi.mocked(stats).mockResolvedValue({} as Awaited<ReturnType<typeof stats>>);
    const result = await ensureHoyoplayGameWine({
      aria2,
      baseWine,
      gameId: "genshin",
      wineTag: DEFAULT_WINE_DISTRIBUTION,
    }).next();
    expect(result.done).toBe(true);
    const wine = result.value as Awaited<Wine>;
    expect(wine.prefix).toBe(baseWine.prefix);
    await wine.exec("synthetic.exe", [], { KEPT: "yes" });
    expect(exec).toHaveBeenCalledWith(
      [
        "/isolated/hoyoplay-wines/genshin/11.0-dxmt-signed-with-patches/wine/bin/wine64",
        "synthetic.exe",
      ],
      {
        WINEDEBUG: "fixme-all,err-unwind,+timestamp",
        WINEPREFIX: baseWine.prefix,
        KEPT: "yes",
      },
      false,
      undefined
    );
  });

  it("keeps the unavailable fresh distribution on the existing download flow", async () => {
    const program = ensureHoyoplayGameWine({
      aria2,
      baseWine,
      gameId: "genshin",
      wineTag: DEFAULT_WINE_DISTRIBUTION,
    });
    expect(await program.next()).toEqual({
      done: false,
      value: ["setStateText", "DOWNLOADING_ENVIRONMENT"],
    });
    expect(exec).not.toHaveBeenCalled();
  });
});

describe("Genshin initial Wine installation guard", () => {
  const installer = vi.fn();
  async function planAndCreateInstaller() {
    const distribution = await getHoyoplayWineInstallationDistribution();
    await prepareFreshHoyoplayWineSelection("genshin");
    installer(distribution);
    return distribution;
  }

  it("allows genuine fresh installation and reserves the canonical selection", async () => {
    const result = await planAndCreateInstaller();
    expect(result.id).toBe(DEFAULT_WINE_DISTRIBUTION);
    expect(installer).toHaveBeenCalledTimes(1);
    expect(preferences.get("hoyoplay_genshin_wine_tag")).toBe(
      DEFAULT_WINE_DISTRIBUTION
    );
  });

  it("keeps known saved global distribution when state and files are absent", async () => {
    preferences.set("wine_tag", "9.9-dxmt");
    const result = await planAndCreateInstaller();
    expect(result.id).toBe("9.9-dxmt");
    expect(setKey).not.toHaveBeenCalled();
  });

  it.each(["wine", "wineprefix"])(
    "blocks an unready existing %s before installer creation",
    async entry => {
      readDirectory.mockResolvedValue([{ entry, type: "DIRECTORY" }]);
      await expect(planAndCreateInstaller()).rejects.toThrow(
        "existing Wine installation or prefix"
      );
      expect(installer).not.toHaveBeenCalled();
      expect(setKey).not.toHaveBeenCalled();
    }
  );

  it("blocks unknown saved distribution instead of falling back", async () => {
    preferences.set("wine_tag", "unknown-legacy");
    await expect(planAndCreateInstaller()).rejects.toThrow(
      "saved Wine distribution is unknown"
    );
    expect(installer).not.toHaveBeenCalled();
    expect(setKey).not.toHaveBeenCalled();
  });

  it("blocks missing distribution with existing ready state", async () => {
    preferences.set("wine_state", "ready");
    await expect(planAndCreateInstaller()).rejects.toThrow(
      "state exists without a distribution"
    );
    expect(installer).not.toHaveBeenCalled();
  });

  it("blocks unrecognized setup state even with a known saved distribution", async () => {
    preferences.set("wine_state", "corrupt-state");
    preferences.set("wine_tag", "9.9-dxmt");
    await expect(planAndCreateInstaller()).rejects.toThrow(
      "setup state is unrecognized"
    );
    expect(installer).not.toHaveBeenCalled();
  });

  it("preserves an explicit recognized update and any per-game selection", async () => {
    preferences.set("wine_state", "update");
    preferences.set("wine_update_tag", "9.9-dxmt");
    preferences.set("hoyoplay_genshin_wine_tag", DEFAULT_WINE_DISTRIBUTION);
    readDirectory.mockResolvedValue([
      { entry: "wineprefix", type: "DIRECTORY" },
    ]);
    expect((await planAndCreateInstaller()).id).toBe("9.9-dxmt");
    expect(installer).toHaveBeenCalledTimes(1);
    expect(setKey).not.toHaveBeenCalled();
  });

  it.each([undefined, "unknown-update"])(
    "blocks missing/unknown pending update %j",
    async update => {
      preferences.set("wine_state", "update");
      if (update !== undefined) preferences.set("wine_update_tag", update);
      await expect(planAndCreateInstaller()).rejects.toThrow(
        "pending Wine distribution is missing or unknown"
      );
      expect(installer).not.toHaveBeenCalled();
      expect(setKey).not.toHaveBeenCalled();
    }
  );

  it("fails closed when installation directory cannot be inspected", async () => {
    readDirectory.mockRejectedValue(new Error("Permission denied"));
    await expect(planAndCreateInstaller()).rejects.toThrow(
      "directory could not be inspected"
    );
    expect(installer).not.toHaveBeenCalled();
    expect(setKey).not.toHaveBeenCalled();
  });

  it("does not mistake a storage API failure for absent preferences", async () => {
    vi.mocked(getKey).mockRejectedValue({ code: "NE_RT_APIPRME" });
    await expect(planAndCreateInstaller()).rejects.toThrow(
      "configuration could not be read"
    );
    expect(installer).not.toHaveBeenCalled();
    expect(setKey).not.toHaveBeenCalled();
  });

  it("keeps an interrupted fresh reservation but blocks replacement of its partial files", async () => {
    await prepareFreshHoyoplayWineSelection("genshin");
    readDirectory.mockResolvedValue([
      { entry: "wineprefix", type: "DIRECTORY" },
    ]);
    await expect(planAndCreateInstaller()).rejects.toThrow(
      "existing Wine installation or prefix"
    );
    expect(installer).not.toHaveBeenCalled();
    expect(preferences.get("hoyoplay_genshin_wine_tag")).toBe(
      DEFAULT_WINE_DISTRIBUTION
    );
    expect(setKey).toHaveBeenCalledTimes(1);
  });
});

// Execute the actual app's unready-Wine branch with inert installer/inputs.
// This catches a guard moved after installer construction or a returned distro
// discarded by app integration, without running createApp's native startup.
function isolatedAppInstallBranch(
  channel = "hoyoplay",
  installer = vi.fn(async options => options)
) {
  const source = readFileSync(new URL("../app.tsx", import.meta.url), "utf8");
  const file = ts.createSourceFile(
    "app.tsx",
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX
  );
  let branch: ts.Statement | undefined;
  const visit = (node: ts.Node) => {
    if (
      ts.isIfStatement(node) &&
      node.expression.getText(file) === "wineStatus.wineReady"
    ) {
      branch = node.elseStatement;
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  if (!branch) throw new Error("App Wine-install branch not found");
  const body = branch
    .getText(file)
    .replaceAll("import.meta.env.YAAGL_CHANNEL_CLIENT", "channel");
  const program = ts.transpileModule(
    `async function run() { let MainApp; ${body}; return MainApp; }`,
    {
      compilerOptions: {
        target: ts.ScriptTarget.ES2020,
        module: ts.ModuleKind.None,
      },
    }
  ).outputText;
  return new Function(
    "channel",
    "wineStatus",
    "getHoyoplayWineInstallationDistribution",
    "prepareFreshHoyoplayWineSelection",
    "createWineInstallProgram",
    "aria2",
    "prefixPath",
    "locale",
    `${program}; return run;`
  )(
    channel,
    { wineDistribution: { id: DEFAULT_WINE_DISTRIBUTION } },
    getHoyoplayWineInstallationDistribution,
    prepareFreshHoyoplayWineSelection,
    installer,
    {},
    "/unchanged/prefix",
    {}
  ) as () => Promise<{ wineDistro: { id: string }; wineAbsPrefix: string }>;
}

describe("actual app initial-installer integration", () => {
  it.each(["hoyoplay", "hoyoplaycn"])(
    "passes the verified saved distribution and original prefix for %s",
    async channel => {
      preferences.set("wine_tag", "9.9-dxmt");
      const options = await isolatedAppInstallBranch(channel)();
      expect(options.wineDistro.id).toBe("9.9-dxmt");
      expect(options.wineAbsPrefix).toBe("/unchanged/prefix");
      expect(setKey).not.toHaveBeenCalled();
    }
  );

  it("stops before constructing the installer on incomplete existing files", async () => {
    readDirectory.mockResolvedValue([
      { entry: "wineprefix", type: "DIRECTORY" },
    ]);
    const installer = vi.fn();
    await expect(
      isolatedAppInstallBranch("hoyoplay", installer)()
    ).rejects.toThrow("existing Wine installation or prefix");
    expect(installer).not.toHaveBeenCalled();
    expect(setKey).not.toHaveBeenCalled();
  });

  it("reserves a genuine fresh preference and passes the verified default", async () => {
    const options = await isolatedAppInstallBranch()();
    expect(options.wineDistro.id).toBe(DEFAULT_WINE_DISTRIBUTION);
    expect(preferences.get("hoyoplay_genshin_wine_tag")).toBe(
      DEFAULT_WINE_DISTRIBUTION
    );
  });

  it("does not overwrite an unreadable per-game preference or construct its installer", async () => {
    vi.mocked(getKey).mockImplementation(async key => {
      if (key === "hoyoplay_genshin_wine_tag") {
        throw { code: "NE_RT_APIPRME" };
      }
      throw { code: "NE_ST_NOSTKEX" };
    });
    await expect(getHoyoplayGameWineTag("genshin")).rejects.toThrow(
      "configuration could not be read"
    );
    await expect(prepareFreshHoyoplayWineSelection("genshin")).rejects.toThrow(
      "configuration could not be read"
    );
    const installer = vi.fn();
    await expect(
      isolatedAppInstallBranch("hoyoplay", installer)()
    ).rejects.toThrow("configuration could not be read");
    expect(installer).not.toHaveBeenCalled();
    expect(setKey).not.toHaveBeenCalled();
  });

  it("does not reinterpret unreadable global metadata as a fresh fallback", async () => {
    vi.mocked(getKey).mockImplementation(async key => {
      if (key === "wine_tag") throw { code: "NE_RT_APIPRME" };
      throw { code: "NE_ST_NOSTKEX" };
    });
    await expect(getHoyoplayGameWineTag("genshin")).rejects.toThrow(
      "configuration could not be read"
    );
    await expect(prepareFreshHoyoplayWineSelection("genshin")).rejects.toThrow(
      "configuration could not be read"
    );
    expect(setKey).not.toHaveBeenCalled();
  });

  it("does not alter the non-HoYoPlay installer path", async () => {
    readDirectory.mockRejectedValue(new Error("Must not inspect"));
    const options = await isolatedAppInstallBranch("hk4eos")();
    expect(options.wineDistro.id).toBe(DEFAULT_WINE_DISTRIBUTION);
    expect(readDirectory).not.toHaveBeenCalled();
    expect(setKey).not.toHaveBeenCalled();
  });
});
