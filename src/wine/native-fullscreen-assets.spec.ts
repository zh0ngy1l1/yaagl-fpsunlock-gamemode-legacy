import { beforeEach, expect, it, vi } from "vitest";
import { exec, mkdirp, readFile, writeBinary } from "@utils";
import {
  nativeFullscreenSupportDirectory,
  NATIVE_FULLSCREEN_PAYLOAD_CHECKSUM,
} from "./native-fullscreen-assets";

vi.mock("@utils", () => ({
  exec: vi.fn(),
  mkdirp: vi.fn(),
  readFile: vi.fn(),
  writeBinary: vi.fn(),
  resolve: (path: string) => "/app/" + path.replace(/^\.\//, ""),
}));
const fetchAsset = vi.fn();
beforeEach(() => {
  vi.resetAllMocks();
  vi.stubGlobal("fetch", fetchAsset);
  vi.mocked(readFile).mockRejectedValue(new Error("Missing sidecar"));
});

it("uses matching full-app support without extracting or changing signed files", async () => {
  vi.mocked(readFile).mockResolvedValue(NATIVE_FULLSCREEN_PAYLOAD_CHECKSUM);
  expect(await nativeFullscreenSupportDirectory()).toBe(
    "/app/sidecar/native-fullscreen"
  );
  expect(fetchAsset).not.toHaveBeenCalled();
  expect(writeBinary).not.toHaveBeenCalled();
  expect(exec).not.toHaveBeenCalled();
});

it("materializes embedded assets for a resources-only update and checks the native helper", async () => {
  const bytes = new Uint8Array([0, 127, 255]).buffer;
  fetchAsset.mockResolvedValue({ ok: true, arrayBuffer: async () => bytes });
  const directory = await nativeFullscreenSupportDirectory();
  expect(directory).toBe(
    `/app/native-fullscreen-support/${NATIVE_FULLSCREEN_PAYLOAD_CHECKSUM.slice(
      0,
      64
    )}`
  );
  expect(mkdirp).toHaveBeenCalledWith(directory);
  for (const name of [
    "payload.tar.gz",
    "payload.sha256",
    "compatible-ntdll.txt",
    "check-idle",
    "install-support.sh",
  ]) {
    expect(writeBinary).toHaveBeenCalledWith(`${directory}/${name}`, bytes);
  }
  expect(exec).toHaveBeenLastCalledWith([
    "codesign",
    "--verify",
    "--strict",
    `${directory}/check-idle`,
  ]);
});

it("aborts on a missing embedded resource before trying to run a helper", async () => {
  fetchAsset.mockResolvedValue({ ok: false });
  await expect(nativeFullscreenSupportDirectory()).rejects.toThrow(
    "Could not read bundled Native Fullscreen support."
  );
  expect(exec).not.toHaveBeenCalled();
});
