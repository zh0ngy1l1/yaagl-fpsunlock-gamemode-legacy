// Missing preferences use these values without writing them to storage.
// Existing values (including false) retain their canonical keys and types.
export const SETTING_DEFAULTS = {
  config_metalHud: true,
  config_retina: false,
  left_cmd: false,
  config_proxyEnabled: false,
  config_proxyHost: "127.0.0.1:8080",
  config_uiLocale: "en",
  config_hk4e_enable_hdr: false,
  config_patch_off: false,
  config_steam_patch: true,
  config_block_net: false,
  config_resolution_custom: false,
  config_resolution_width: "1920",
  config_resolution_height: "1080",
  config_timeout_fix: true,
} as const;

export const GAME_SETTING_DEFAULTS = {
  fpsUnlockEnabled: true,
  fpsUnlockTarget: 120,
  renderer: "dxmt",
} as const;

export const DEFAULT_WINE_DISTRIBUTION = "11.0-dxmt-signed-with-patches";
