export interface Config {
  // Historical patch metadata compatibility. No current Genshin patch uses
  // this tag; its removed settings UI no longer reads or writes the preference.
  workaround3?: boolean;
}

export const NOOP = async () => {
  return;
};
