import { Box, Checkbox, FormControl, FormLabel, Text } from "@hope-ui/solid";
import { createSignal } from "solid-js";
import { fatal } from "@utils";
import { Config } from "./config-def";
import {
  readNativeFullscreen,
  saveNativeFullscreen,
} from "./native-fullscreen-setting";

declare module "./config-def" {
  interface Config {
    nativeFullscreen: boolean;
  }
}

export async function createNativeFullscreenConfig({
  config,
  supported,
}: {
  config: Partial<Config>;
  supported: () => boolean;
}) {
  const [value, setValue] = createSignal(await readNativeFullscreen());
  const [saving, setSaving] = createSignal(false);
  // Keep the saved preference when changing engines, but never enable an
  // unsupported selection. Launch preparation snapshots this effective value.
  Object.defineProperty(config, "nativeFullscreen", {
    enumerable: true,
    get: () => supported() && value(),
  });
  async function change() {
    if (!supported() || saving()) return;
    setSaving(true);
    try {
      const enabled = !value();
      await saveNativeFullscreen(enabled);
      setValue(enabled);
    } catch (error) {
      fatal(error);
    } finally {
      setSaving(false);
    }
  }
  return function NativeFullscreen() {
    return (
      <FormControl id="nativeFullscreen">
        <FormLabel>Native Fullscreen</FormLabel>
        <Box>
          <Checkbox
            checked={supported() && value()}
            disabled={!supported() || saving()}
            size="md"
            onChange={change}
            aria-describedby="native-fullscreen-description"
          >
            Enabled
          </Checkbox>
        </Box>
        <Text id="native-fullscreen-description" size="xs">
          Use macOS native fullscreen and enable Game Mode while fullscreen.{" "}
          Applies on next launch.
        </Text>
        <Text size="xs">Requires Wine 11.0 DXMT (signed, with patches).</Text>
      </FormControl>
    );
  };
}
