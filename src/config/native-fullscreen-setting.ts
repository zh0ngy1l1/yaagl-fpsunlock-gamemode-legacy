import { getKeyOrDefault, setKey } from "@utils";
import { SETTING_DEFAULTS } from "./defaults";

export async function readNativeFullscreen() {
  return (
    (await getKeyOrDefault(
      "config_nativeFullscreen",
      String(SETTING_DEFAULTS.config_nativeFullscreen)
    )) === "true"
  );
}

export async function saveNativeFullscreen(enabled: boolean) {
  await setKey("config_nativeFullscreen", String(enabled));
}
