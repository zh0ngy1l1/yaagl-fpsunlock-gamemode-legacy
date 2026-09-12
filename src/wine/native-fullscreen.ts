import { exec, readFile } from "@utils";
import { basename } from "path-browserify";
import type { Wine } from "./wine";
import {
  nativeFullscreenSupportDirectory,
  NATIVE_FULLSCREEN_PAYLOAD_CHECKSUM,
} from "./native-fullscreen-assets";

export const NATIVE_FULLSCREEN_DISTRO = "11.0-dxmt-signed-with-patches";
export const NATIVE_FULLSCREEN_ENV = "YAAGL_NATIVE_FULLSCREEN";

export function nativeFullscreenEnvironment(
  distribution: string,
  env: Record<string, string> = {}
) {
  return {
    ...env,
    [NATIVE_FULLSCREEN_ENV]:
      distribution === NATIVE_FULLSCREEN_DISTRO &&
      env[NATIVE_FULLSCREEN_ENV] === "1"
        ? "1"
        : "0",
  };
}

export async function ensureNativeFullscreenEngine(
  wineRoot: string,
  distribution: string
) {
  if (distribution !== NATIVE_FULLSCREEN_DISTRO) return;
  try {
    if (
      (await readFile(`${wineRoot}/.native-fullscreen.sha256`)) ===
      NATIVE_FULLSCREEN_PAYLOAD_CHECKSUM
    )
      return;
  } catch {
    // Upgrade an older supported engine before its first Wine command.
  }
  const support = await nativeFullscreenSupportDirectory();
  // A current installation is a no-op. Upgrades refuse an engine in use.
  await exec(["/bin/bash", `${support}/install-support.sh`, wineRoot, support]);
}

export async function prepareNativeFullscreen(
  wine: Wine,
  requested: boolean,
  gameExecutable: string
) {
  const supported = wine.attributes.distributionId === NATIVE_FULLSCREEN_DISTRO;
  const enabled = supported && requested;
  if (supported) {
    // An explicit app value also overrides stale manual AppDefaults entries.
    for (const key of [
      "HKEY_CURRENT_USER\\Software\\Wine\\Mac Driver",
      `HKEY_CURRENT_USER\\Software\\Wine\\AppDefaults\\${basename(
        gameExecutable
      )}\\Mac Driver`,
    ]) {
      await wine.exec(
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
        { [NATIVE_FULLSCREEN_ENV]: "0" },
        "/dev/null"
      );
    }
    await wine.waitUntilServerOff();
  }
  return { [NATIVE_FULLSCREEN_ENV]: enabled ? "1" : "0" };
}
