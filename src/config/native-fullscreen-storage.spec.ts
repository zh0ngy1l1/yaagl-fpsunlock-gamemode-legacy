import { beforeEach, expect, it, vi } from "vitest";
import { getKey, setKey, withStorageNamespace } from "../utils/neu";

const data = new Map<string, string>();
const files = new Map<string, string>();
beforeEach(() => {
  data.clear();
  files.clear();
  vi.stubGlobal("Neutralino", {
    storage: {
      getData: async (key: string) => {
        if (!data.has(key)) throw Error("missing");
        return data.get(key);
      },
      setData: async (key: string, value: string) => {
        data.set(key, value);
      },
    },
    filesystem: {
      readFile: async (key: string) => {
        if (!files.has(key)) throw Error("missing");
        return files.get(key);
      },
      writeFile: async (key: string, value: string) => {
        files.set(key, value);
      },
    },
    os: {
      getEnv: async () => "/Users/test",
      execCommand: async () => ({ exitCode: 0, stdOut: "", stdErr: "" }),
    },
    debug: { log: async () => undefined },
  });
});
it("uses independent client namespaces and retains Off across reloads", async () => {
  await withStorageNamespace("client-one", () =>
    setKey("config_nativeFullscreen", "true")
  );
  await withStorageNamespace("client-two", () =>
    setKey("config_nativeFullscreen", "false")
  );
  expect(
    await withStorageNamespace("client-one", () =>
      getKey("config_nativeFullscreen")
    )
  ).toBe("true");
  expect(
    await withStorageNamespace("client-two", () =>
      getKey("config_nativeFullscreen")
    )
  ).toBe("false");
});
it("uses the same Genshin compatibility storage route as neighboring Metal HUD", async () => {
  await withStorageNamespace("hpgenshin", async () => {
    await setKey("config_nativeFullscreen", "false");
    await setKey("config_metalHud", "true");
    expect(await getKey("config_nativeFullscreen")).toBe("false");
    expect(await getKey("config_metalHud")).toBe("true");
  });
  expect([...files.keys()]).toEqual([
    "/Users/test/Library/Application Support/Yaagl OS/.storage/config_nativeFullscreen.neustorage",
    "/Users/test/Library/Application Support/Yaagl OS/.storage/config_metalHud.neustorage",
  ]);
});
