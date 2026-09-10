import { Aria2 } from "@aria2";
import { CommonUpdateProgram } from "@common-update-ui";
import { createConfiguration, type ConfigurationUIProps } from "@config";
import { Locale } from "@locale";
import {
  activateStorageNamespace,
  fatal,
  humanDuration,
  humanFileSize,
  openDir,
  withStorageNamespace,
} from "@utils";
import { Wine } from "@wine";
import {
  Button,
  Modal,
  ModalFooter,
  ModalOverlay,
  Progress,
  ProgressIndicator,
} from "@hope-ui/solid";
import { Accessor, For, JSXElement, Show, createSignal } from "solid-js";
import { createGameInstallationDirectorySanitizer } from "../accidental-complexity";
import { ChannelClient } from "../channel-client";
import { Config } from "../config/config-def";
import { GAME_SETTING_DEFAULTS } from "../config/defaults";
import type { Github } from "../github";
import { createClient as createGenshinOsClient } from "../clients/hk4eos";
import { createHoyoplayTaskQueueState } from "./hoyoplay-task-queue";
import {
  createDelayedCompanion,
  ensureGenshinFpsUnlocker,
  getFpsConfig,
  setFpsConfig,
  startGenshinFpsUnlockScript,
  withD3DMetalPerformanceEnv,
  withDxmtPreferredMaxFrameRate,
  withWineExec2Transform,
} from "./hoyoplay-injections";
import {
  createHoyoplayWineProxy,
  ensureHoyoplayGameWine,
  ensureHoyoplayD3DMetalRuntime,
  getHoyoplayD3DMetalPath,
  getHoyoplayGameWineTag,
  getHoyoplayGameRenderer,
  getHoyoplayWineBin,
  getHoyoplayWineOptions,
  HOYOPLAY_RENDERER_D3DMETAL,
  HOYOPLAY_RENDERER_DXMT,
  setHoyoplayGameRenderer,
  setHoyoplayGameWineTag,
  SHARED_WINE_TAG,
  type HoyoplayWineRef,
  type HoyoplayRenderer,
} from "./hoyoplay-wine";

type HoyoplayGameId = "genshin";

export type HoyoplayGameSpec = {
  id: HoyoplayGameId;
  namespace: string;
  title: string;
  fpsSupported: boolean;
  createClient: (options: {
    wine: Wine;
    aria2: Aria2;
    locale: Locale;
  }) => Promise<ChannelClient>;
};

type GameState = {
  id: HoyoplayGameId;
  namespace: string;
  title: string;
  client: ChannelClient;
  config: Config;
  ConfigurationUI: (props: ConfigurationUIProps) => JSXElement;
  fpsSupported: boolean;
  fpsEnabled: Accessor<boolean>;
  setFpsEnabled: (value: boolean) => void;
  fpsTarget: Accessor<string>;
  setFpsTarget: (value: string) => void;
  wineRef: HoyoplayWineRef;
  wineTag: Accessor<string>;
  setWineTag: (value: string) => void;
  renderer: Accessor<HoyoplayRenderer>;
  setRenderer: (value: HoyoplayRenderer) => void;
  wineOptions: {
    tag: string;
    displayName: string;
    url: string;
    disabled?: boolean;
  }[];
};

export const DEFAULT_HOYOPLAY_GAME_SPECS: HoyoplayGameSpec[] = [
  {
    id: "genshin",
    namespace: "hpgenshin",
    title: "Genshin Impact",
    fpsSupported: true,
    createClient: createGenshinOsClient,
  },
];

function sanitizeFps(value: string) {
  const fps = Math.trunc(Number(value));
  return Number.isFinite(fps) && fps > 0
    ? fps
    : GAME_SETTING_DEFAULTS.fpsUnlockTarget;
}

function namespacedProgram(
  aria2: Aria2,
  baseWine: Wine,
  game: GameState,
  d3dmetalPath: Accessor<string>,
  program: () => CommonUpdateProgram
): () => CommonUpdateProgram {
  return async function* () {
    game.wineRef.current = yield* ensureHoyoplayGameWine({
      aria2,
      baseWine,
      gameId: game.id,
      wineTag: game.wineTag(),
      renderer: game.renderer(),
      d3dmetalPath: d3dmetalPath(),
    });
    const iterator = await withStorageNamespace(game.namespace, async () =>
      program()
    );
    while (true) {
      const result = await withStorageNamespace(game.namespace, async () =>
        iterator.next()
      );
      if (result.done) return;
      yield result.value;
    }
  };
}

export async function createHoyoplayLauncher({
  wine,
  locale,
  aria2,
  github,
  onCheckUpdate,
  appSupportName = "Yaagl OS",
  specs = DEFAULT_HOYOPLAY_GAME_SPECS,
}: {
  wine: Wine;
  locale: Locale;
  aria2: Aria2;
  github: Github;
  onCheckUpdate: () => void;
  appSupportName?: string;
  specs?: HoyoplayGameSpec[];
}) {
  const baseWine = wine;
  const initialD3DMetalPath = await getHoyoplayD3DMetalPath();
  const [d3dmetalPath, setD3DMetalPath] = createSignal(initialD3DMetalPath);

  const games: GameState[] = [];

  for (const spec of specs) {
    const wineRef: HoyoplayWineRef = { current: baseWine };
    const gameWine = createHoyoplayWineProxy(wineRef);
    const client = await withStorageNamespace(spec.namespace, async () =>
      spec.createClient({ wine: gameWine, aria2, locale })
    );
    const { UI: ConfigurationUI, config } = await withStorageNamespace(
      spec.namespace,
      async () =>
        createConfiguration({
          wine: gameWine,
          locale,
          gameInstallDir: client.installDir,
          configForChannelClient: client.createConfig,
          onCheckUpdate,
        })
    );
    const fps = await getFpsConfig(spec.id);
    const [fpsEnabled, setFpsEnabled] = createSignal(fps.enabled);
    const [fpsTarget, setFpsTarget] = createSignal(String(fps.target));
    const initialWineTag = await getHoyoplayGameWineTag(spec.id);
    const [wineTag, setWineTag] = createSignal(initialWineTag);
    const initialRenderer = await getHoyoplayGameRenderer(spec.id);
    const [renderer, setRenderer] =
      createSignal<HoyoplayRenderer>(initialRenderer);
    const wineOptions = await getHoyoplayWineOptions(initialWineTag);

    games.push({
      ...spec,
      client,
      config: config as Config,
      ConfigurationUI,
      fpsEnabled,
      setFpsEnabled,
      fpsTarget,
      setFpsTarget,
      wineRef,
      wineTag,
      setWineTag,
      renderer,
      setRenderer,
      wineOptions,
    });
  }

  const { selectPath } = await createGameInstallationDirectorySanitizer({
    openFolderDialog: async () =>
      await openDir(locale.get("SELECT_INSTALLATION_DIR")),
    locale,
  });

  function launchProgram(game: GameState): CommonUpdateProgram {
    return (async function* () {
      const fpsEnabled = game.fpsSupported && game.fpsEnabled();
      const fpsTarget = sanitizeFps(game.fpsTarget());
      const activeWine = game.wineRef.current;
      const renderer = game.renderer();

      if (
        renderer === HOYOPLAY_RENDERER_D3DMETAL &&
        game.wineTag() === SHARED_WINE_TAG
      ) {
        throw new Error(
          "D3DMetal requires a per-game Wine selection. Choose a Wine Distribution instead of the existing inherited runtime so its files stay untouched."
        );
      }
      if (renderer === HOYOPLAY_RENDERER_D3DMETAL) {
        const runtimePath = yield* ensureHoyoplayD3DMetalRuntime({
          aria2,
          github,
        });
        setD3DMetalPath(runtimePath);
      }

      if (game.id === "genshin" && fpsEnabled) {
        yield* ensureGenshinFpsUnlocker(aria2, activeWine);
      }

      const shouldTransformEnv =
        renderer === HOYOPLAY_RENDERER_D3DMETAL ||
        (fpsEnabled && game.id === "genshin");
      let fpsUnlockerEnv: Record<string, string> = {};
      const fpsUnlockerCompanion =
        game.id === "genshin" && fpsEnabled
          ? createDelayedCompanion(async () => {
              const launchEnv = fpsUnlockerEnv;
              const unlockerWineBin = await getHoyoplayWineBin(
                game.id,
                game.wineTag()
              );
              return startGenshinFpsUnlockScript(
                activeWine,
                fpsTarget,
                unlockerWineBin,
                launchEnv
              );
            })
          : undefined;
      const launchWithEnv = () =>
        shouldTransformEnv
          ? withWineExec2Transform(
              activeWine,
              env => {
                const d3dmetalEnv =
                  renderer === HOYOPLAY_RENDERER_D3DMETAL
                    ? withD3DMetalPerformanceEnv(env)
                    : env;
                return fpsEnabled && renderer === HOYOPLAY_RENDERER_DXMT
                  ? withDxmtPreferredMaxFrameRate(d3dmetalEnv, fpsTarget)
                  : d3dmetalEnv;
              },
              () => game.client.launch(game.config),
              fpsUnlockerCompanion && {
                start(env) {
                  fpsUnlockerEnv = env;
                  fpsUnlockerCompanion.schedule();
                },
                stop() {
                  return fpsUnlockerCompanion.stop();
                },
              },
              game.id === "genshin" &&
                fpsEnabled &&
                renderer === HOYOPLAY_RENDERER_DXMT &&
                fpsTarget > 60
                ? env => withDxmtPreferredMaxFrameRate(env, 0)
                : undefined
            )
          : game.client.launch(game.config);

      try {
        yield* launchWithEnv();
      } finally {
        await fpsUnlockerCompanion?.stop();
      }
    })();
  }

  return function HoyoplayLauncher() {
    // HoYoPlay selections were never persisted by this launcher. Always use
    // its Genshin entry; unrelated legacy storage keys and data stay untouched.
    const selectedGame = () => games[0];
    const [nativeSettingsGame, setNativeSettingsGame] =
      createSignal<GameState>();
    const [videoLoaded, setVideoLoaded] = createSignal(false);
    let restoreNativeSettingsNamespace: (() => void) | undefined;
    const [
      statusText,
      progress,
      programBusy,
      taskQueue,
      downloadEta,
      estimatedSpeedBps,
      setPendingSizeBytes,
    ] = createHoyoplayTaskQueueState({ locale });

    games.forEach(game => {
      // Skip the startup patch-revert/integrity-check pass for a game that's
      // already known to need an update: repairing a stale install against
      // the latest manifest aborts instead of prompting to update.
      if (game.client.updateRequired()) return;
      taskQueue.next(
        namespacedProgram(aria2, baseWine, game, d3dmetalPath, () =>
          game.client.init(game.config)
        )
      );
    });

    async function saveWineSettings(game: GameState) {
      await setHoyoplayGameWineTag(game.id, game.wineTag());
    }

    async function saveRendererSettings(game: GameState) {
      await setHoyoplayGameRenderer(game.id, game.renderer());
    }

    async function saveFpsSettings(game: GameState) {
      const fps = sanitizeFps(game.fpsTarget());
      game.setFpsTarget(String(fps));
      await setFpsConfig(game.id, game.fpsEnabled(), String(fps));
    }

    async function onPrimaryAction() {
      if (programBusy()) return;
      const game = selectedGame();
      await saveWineSettings(game);
      await saveRendererSettings(game);
      await saveFpsSettings(game);

      if (game.client.installState() === "INSTALLED") {
        if (game.client.updateRequired()) {
          setPendingSizeBytes(game.client.updateSizeBytes?.() ?? 0);
          taskQueue.next(
            namespacedProgram(aria2, baseWine, game, d3dmetalPath, () =>
              game.client.update()
            )
          );
        } else {
          taskQueue.next(
            namespacedProgram(aria2, baseWine, game, d3dmetalPath, () =>
              launchProgram(game)
            )
          );
        }
      } else {
        const selection = await selectPath();
        if (!selection) return;
        taskQueue.next(
          namespacedProgram(aria2, baseWine, game, d3dmetalPath, () =>
            game.client.install(selection)
          )
        );
      }
    }

    function actionLabel(game: GameState) {
      if (game.client.installState() !== "INSTALLED")
        return locale.get("INSTALL");
      if (!game.client.updateRequired()) return locale.get("LAUNCH");
      const sizeBytes = game.client.updateSizeBytes?.() ?? 0;
      if (sizeBytes <= 0) return locale.get("UPDATE");
      const speedBps = estimatedSpeedBps();
      const etaSuffix =
        speedBps > 0 ? `, ~${humanDuration(sizeBytes / speedBps)}` : "";
      return `${locale.get("UPDATE")} (${humanFileSize(
        sizeBytes
      )}${etaSuffix})`;
    }

    function selectedInstallLabel() {
      const game = selectedGame();
      if (game.client.installState() !== "INSTALLED") return "Not installed";
      return game.client.updateRequired() ? "Update available" : "Ready";
    }

    function onPredownload() {
      const game = selectedGame();
      taskQueue.next(
        namespacedProgram(aria2, baseWine, game, d3dmetalPath, () =>
          game.client.predownload()
        )
      );
    }

    function openNativeSettings(game: GameState) {
      restoreNativeSettingsNamespace?.();
      restoreNativeSettingsNamespace = activateStorageNamespace(game.namespace);
      setNativeSettingsGame(game);
    }

    function closeNativeSettings() {
      restoreNativeSettingsNamespace?.();
      restoreNativeSettingsNamespace = undefined;
      setNativeSettingsGame(undefined);
    }

    return (
      <div
        class="hoyoplay-shell"
        style={{
          "background-image": selectedGame().client.uiContent.background
            ? `url(${selectedGame().client.uiContent.background})`
            : undefined,
        }}
      >
        <Show when={selectedGame().client.uiContent.background_video}>
          <video
            class="hoyoplay-video"
            src={selectedGame().client.uiContent.background_video}
            autoplay
            loop
            muted
            playsinline
            onLoadedData={() => setVideoLoaded(true)}
            style={{ opacity: videoLoaded() ? 1 : 0 }}
          />
        </Show>
        <Show when={selectedGame().client.uiContent.background_theme}>
          <div
            class="hoyoplay-theme"
            style={{
              "background-image": `url(${
                selectedGame().client.uiContent.background_theme
              })`,
            }}
          />
        </Show>

        <main class="hoyoplay-stage" aria-label={selectedGame().title}>
          <section
            class="hoyoplay-action-area"
            classList={{
              "hoyoplay-action-left":
                selectedGame().client.uiContent.launchButtonLocation === "left",
            }}
          >
            <div class="hoyoplay-progress" role="status" aria-live="polite">
              <Show when={programBusy()}>
                <strong>
                  {statusText()}
                  {downloadEta() ? ` — ETA ${downloadEta()}` : ""}
                </strong>
                <Progress
                  value={progress()}
                  indeterminate={progress() === 0}
                  size="sm"
                  borderRadius={8}
                >
                  <ProgressIndicator
                    style={"transition: none;"}
                    borderRadius={8}
                  />
                </Progress>
              </Show>
            </div>
            <div class="hoyoplay-launch-panel">
              <Show
                when={
                  selectedGame().client.showPredownloadPrompt() &&
                  !programBusy()
                }
              >
                <div class="hoyoplay-predownload">
                  <button onClick={onPredownload}>
                    {locale.format("PREDOWNLOAD_READY", [
                      selectedGame().client.predownloadVersion(),
                    ])}
                  </button>
                </div>
              </Show>
              <Show when={selectedGame().fpsSupported}>
                <button
                  class="hoyoplay-fps-summary"
                  onClick={() => openNativeSettings(selectedGame())}
                >
                  {locale.get("SETTING_FPS_UNLOCK")}:{" "}
                  {selectedGame().fpsEnabled()
                    ? `${selectedGame().fpsTarget()} FPS`
                    : locale.get("SETTING_FPS_UNLOCK_DEFAULT")}
                </button>
              </Show>
              <div class="hoyoplay-button-group">
                <Button
                  class="hoyoplay-launch-button"
                  size="xl"
                  disabled={programBusy()}
                  onClick={() => onPrimaryAction().catch(fatal)}
                  title={selectedInstallLabel()}
                >
                  {actionLabel(selectedGame())}
                </Button>
                <Button
                  class="hoyoplay-settings-button"
                  size="xl"
                  aria-label={locale.get("SETTING")}
                  title={locale.get("SETTING")}
                  onClick={() => openNativeSettings(selectedGame())}
                >
                  <span class="hoyoplay-settings-icon" aria-hidden="true">
                    ⚙
                  </span>
                </Button>
              </div>
            </div>
          </section>
        </main>

        <Modal
          opened={!!nativeSettingsGame()}
          onClose={closeNativeSettings}
          scrollBehavior="inside"
        >
          <ModalOverlay />
          <Show when={nativeSettingsGame()}>
            {game => {
              const UI = game().ConfigurationUI;
              return (
                <UI
                  gameSettings={
                    <Show when={game().fpsSupported}>
                      <div class="hoyoplay-game-settings">
                        <label class="hoyoplay-setting-row">
                          <span>{locale.get("SETTING_FPS_UNLOCK")}</span>
                          <input
                            type="checkbox"
                            checked={game().fpsEnabled()}
                            onInput={event =>
                              game().setFpsEnabled(event.currentTarget.checked)
                            }
                          />
                        </label>
                        <label class="hoyoplay-setting-row">
                          <span>Target FPS</span>
                          <input
                            type="number"
                            min="1"
                            step="1"
                            value={game().fpsTarget()}
                            onInput={event =>
                              game().setFpsTarget(event.currentTarget.value)
                            }
                          />
                        </label>
                        <p class="hoyoplay-settings-muted">
                          The numeric target is saved for this game. Launching
                          applies the selected FPS unlock setting.
                        </p>
                      </div>
                    </Show>
                  }
                  wineSettings={
                    <div class="hoyoplay-game-settings">
                      <label class="hoyoplay-setting-row">
                        <span>Wine Distribution</span>
                        <select
                          value={game().wineTag()}
                          title={
                            game().wineOptions.find(
                              item => item.tag === game().wineTag()
                            )?.displayName
                          }
                          onInput={event =>
                            game().setWineTag(event.currentTarget.value)
                          }
                        >
                          <For each={game().wineOptions}>
                            {item => (
                              <option value={item.tag} disabled={item.disabled}>
                                {item.displayName}
                              </option>
                            )}
                          </For>
                        </select>
                      </label>
                      <label class="hoyoplay-setting-row">
                        <span>Wine Renderer</span>
                        <select
                          value={game().renderer()}
                          onInput={event =>
                            game().setRenderer(
                              event.currentTarget.value as HoyoplayRenderer
                            )
                          }
                        >
                          <option value={HOYOPLAY_RENDERER_DXMT}>DXMT</option>
                          <option value={HOYOPLAY_RENDERER_D3DMETAL}>
                            D3DMetal (experimental)
                          </option>
                        </select>
                      </label>
                      <Show
                        when={game().renderer() === HOYOPLAY_RENDERER_D3DMETAL}
                      >
                        <p class="hoyoplay-settings-muted">
                          D3DMetal is downloaded automatically on first launch
                          and applied only to per-game Wine, so the shared YAAGL
                          Wine stays compatible with older launchers. Cached
                          under{" "}
                          <code>
                            Application Support/{appSupportName}
                            /hoyoplay-renderers
                          </code>
                          .
                        </p>
                      </Show>
                    </div>
                  }
                  settingsFooter={
                    <ModalFooter class="hoyoplay-settings-footer">
                      <Button
                        onClick={() =>
                          Promise.all([
                            saveWineSettings(game()),
                            saveRendererSettings(game()),
                            saveFpsSettings(game()),
                          ]).then(closeNativeSettings)
                        }
                      >
                        {locale.get("SETTING_SAVE")}
                      </Button>
                    </ModalFooter>
                  }
                  onClose={action => {
                    const savedGame = game();
                    closeNativeSettings();
                    if (action === "check-integrity") {
                      taskQueue.next(
                        namespacedProgram(
                          aria2,
                          baseWine,
                          savedGame,
                          d3dmetalPath,
                          () => savedGame.client.checkIntegrity()
                        )
                      );
                    }
                  }}
                />
              );
            }}
          </Show>
        </Modal>
      </div>
    );
  };
}
