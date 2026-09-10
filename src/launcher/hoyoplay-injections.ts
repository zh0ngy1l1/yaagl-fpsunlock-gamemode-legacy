import type { Aria2 } from "@aria2";
import { GAME_SETTING_DEFAULTS } from "@config/defaults";
import type { CommonUpdateProgram } from "@common-update-ui";
import {
  exec,
  fileOrDirExists,
  getKeyOrDefault,
  humanFileSize,
  mkdirp,
  resolve,
  setKey,
  spawn,
  writeFile,
} from "@utils";
import type { Wine } from "@wine";
import { join } from "path-browserify";
import { resolveFpsTarget } from "./fps-target";

const FPS_UNLOCKER_URL =
  "https://github.com/rishabhroyy/genshin-fps-unlock-universal/releases/download/v3.0.7/unlockfps.exe";

function shellQuote(value: string) {
  return `'${value.replaceAll("'", `'\\''`)}'`;
}

export async function* ensureGenshinFpsUnlocker(
  aria2: Aria2,
  wine: Wine
): CommonUpdateProgram {
  const dir = join(wine.prefix, "drive_c", "fps-unlocker");
  const exe = join(dir, "unlockfps.exe");
  if (await fileOrDirExists(exe)) return;

  await mkdirp(dir);
  yield ["setStateText", "DOWNLOADING_ENVIRONMENT"];
  for await (const progress of aria2.doStreamingDownload({
    uri: FPS_UNLOCKER_URL,
    absDst: exe,
  })) {
    yield [
      "setProgress",
      Number((progress.completedLength * BigInt(100)) / progress.totalLength),
    ];
    yield [
      "setStateText",
      "DOWNLOADING_ENVIRONMENT_SPEED",
      `${humanFileSize(Number(progress.downloadSpeed))}`,
    ];
  }
}

export async function startGenshinFpsUnlockScript(
  wine: Wine,
  fps: number,
  wineBin = resolve("./wine/bin/wine"),
  env: Record<string, string> = {}
) {
  fps = resolveFpsTarget(fps);
  const scriptPath = resolve("./hoyoplay_genshin_fps_unlocker.sh");
  const logPath = resolve("./logs/hoyoplay_genshin_fps_unlocker.log");

  await writeFile(
    scriptPath,
    [
      "#!/bin/bash",
      "set +e",
      `export WINEPREFIX=${shellQuote(wine.prefix)}`,
      `WINE=${shellQuote(wineBin)}`,
      `LOG=${shellQuote(logPath)}`,
      "",
      `mkdir -p "$(dirname "$LOG")"`,
      `exec >> "$LOG" 2>&1`,
      `echo "----- $(date) -----"`,
      `echo "WINE=$WINE"`,
      `echo "WINEPREFIX=$WINEPREFIX"`,
      `env | grep -E '^(WINE|WINEMSYNC|WINEESYNC|WINEFSYNC|D3DM|DXMT|MTL|GST_|ROSETTA_)' | sort`,
      "",
      "UNLOCKER_PID=",
      `cleanup() {`,
      `  if [ -n "$UNLOCKER_PID" ]; then`,
      `    kill "$UNLOCKER_PID" 2>/dev/null`,
      `    wait "$UNLOCKER_PID" 2>/dev/null`,
      `  fi`,
      `  exit`,
      `}`,
      `trap cleanup INT TERM EXIT`,
      "",
      `game_running() {`,
      `  "$WINE" tasklist.exe 2>/dev/null | grep -Eiq 'GenshinImpact|YuanShen'`,
      `}`,
      "",
      `echo "Waiting for Genshin process..."`,
      `for _ in $(seq 1 90); do`,
      `  if game_running; then`,
      `    echo "Genshin process detected."`,
      `    break`,
      `  fi`,
      `  sleep 1`,
      `done`,
      "",
      `echo "Waiting for game initialization before starting unlocker..."`,
      `sleep 10`,
      "",
      `while game_running; do`,
      `  echo "Starting unlockfps.exe with target ${fps}..."`,
      `  "$WINE" "C:\\\\fps-unlocker\\\\unlockfps.exe" ${fps} &`,
      `  UNLOCKER_PID=$!`,
      `  while kill -0 "$UNLOCKER_PID" 2>/dev/null; do`,
      `    if ! game_running; then`,
      `      echo "Genshin process disappeared; stopping unlocker."`,
      `      kill "$UNLOCKER_PID" 2>/dev/null`,
      `      break`,
      `    fi`,
      `    sleep 1`,
      `  done`,
      `  wait "$UNLOCKER_PID" 2>/dev/null`,
      `  EXIT_CODE=$?`,
      `  UNLOCKER_PID=`,
      `  echo "unlockfps.exe exited with code $EXIT_CODE."`,
      `  if ! game_running; then`,
      `    echo "Genshin process is gone; unlocker script exiting."`,
      `    break`,
      `  fi`,
      `  echo "Genshin is still running; retrying unlocker in 5s."`,
      `  sleep 5`,
      `done`,
      "",
      `echo "Cleaning up companion Wine processes."`,
      `"$WINE" taskkill.exe /F /IM unlockfps.exe 2>/dev/null`,
      `"$WINE" taskkill.exe /F /IM steam.exe 2>/dev/null`,
      "",
    ].join("\n")
  );

  const process = await spawn(["bash", scriptPath], env);
  return {
    async stop() {
      try {
        await Neutralino.os.updateSpawnedProcess(process.id, "exit");
      } catch {
        // Fall back to killing the shell process below.
      }
      try {
        await exec(["kill", process.pid + ""]);
      } catch {
        // Already exited.
      }
    },
  };
}

export function createDelayedCompanion(
  start: () => Promise<{ stop(): Promise<void> }>,
  delayMs = 10000
): { schedule(): void; stop(): Promise<void> } {
  let scheduled = false;
  let stopped = false;
  let companion: { stop(): Promise<void> } | undefined;
  let startPromise: Promise<void> | undefined;
  let stopPromise: Promise<void> | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;

  return {
    schedule() {
      if (scheduled || stopped) return;
      scheduled = true;
      timer = setTimeout(() => {
        startPromise = start().then(async started => {
          if (stopped) {
            await started.stop();
          } else {
            companion = started;
          }
        });
      }, delayMs);
    },
    async stop() {
      stopPromise ??= (async () => {
        stopped = true;
        if (timer) clearTimeout(timer);
        await startPromise;
        if (companion) await companion.stop();
      })();
      return stopPromise;
    },
  };
}

export async function getFpsConfig(gameId: string) {
  return {
    enabled:
      (await getKeyOrDefault(
        `hoyoplay_${gameId}_fps_enabled`,
        String(GAME_SETTING_DEFAULTS.fpsUnlockEnabled)
      )) == "true",
    // Keep invalid legacy values visible; only an absent preference defaults.
    target: await getKeyOrDefault(
      `hoyoplay_${gameId}_fps`,
      String(GAME_SETTING_DEFAULTS.fpsUnlockTarget)
    ),
  };
}

export function setFpsConfig(gameId: string, enabled: boolean, target: string) {
  const resolvedTarget = resolveFpsTarget(target);
  return Promise.all([
    setFpsUnlockEnabled(gameId, enabled),
    setKey(`hoyoplay_${gameId}_fps`, String(resolvedTarget)),
  ]);
}

export function setFpsUnlockEnabled(gameId: string, enabled: boolean) {
  return setKey(`hoyoplay_${gameId}_fps_enabled`, enabled ? "true" : "false");
}

export function withDxmtPreferredMaxFrameRate(
  env: Record<string, string>,
  fps: number
) {
  const current = env.DXMT_CONFIG ?? "";
  const next = current
    .split(";")
    .filter(entry => !/^\s*d3d11\.preferredMaxFrameRate\s*=/.test(entry))
    .join(";");

  return {
    ...env,
    DXMT_CONFIG: `d3d11.preferredMaxFrameRate=${fps};${next}`,
  };
}

export function withD3DMetalPerformanceEnv(env: Record<string, string>) {
  const next = { ...env };
  delete next.DXMT_CONFIG;
  delete next.DXMT_CONFIG_FILE;
  delete next.DXMT_ENABLE_NVEXT;
  delete next.DXMT_LOG_PATH;
  delete next.MTL_SHADER_VALIDATION;
  delete next.WINEESYNC;
  delete next.WINEFSYNC;
  delete next.D3DM_BOUNDS_CHECK;
  delete next.D3DM_IGNORE_D3D11_RENDER_BARRIERS;
  delete next.D3DM_SHOW_HUD_STATS;
  delete next.D3DM_WAIT_ON_RESET;

  return {
    ...next,
    WINEMSYNC: "1",
    WINEDEBUG: "-all",
    WINE_CPU_TOPOLOGY: "8:0,1,2,3,4,5,6,7",
    ROSETTA_ADVERTISE_AVX: "1",
    D3DM_MULTITHREADED_INTERFACE_ENABLE: "1",
    D3DM_ENABLE_ASYNC_COMMIT: "1",
    D3DM_RETAIN_REFERENCES: "1",
    GST_PLUGIN_FEATURE_RANK: "atdec:MAX,avdec_h264:MAX",
  };
}

export async function* withWineExec2Transform(
  wine: Wine,
  transformEnv: (env: Record<string, string>) => Record<string, string>,
  program: () => CommonUpdateProgram,
  onExec2?: {
    start(env: Record<string, string>): void;
    stop(): Promise<void>;
  },
  transformGameEnv?: (env: Record<string, string>) => Record<string, string>
): CommonUpdateProgram {
  const originalExec2 = wine.exec2.bind(wine);

  wine.exec2 = async (command, args, env, logPath) => {
    const transformedEnv = transformEnv(env ?? {});
    onExec2?.start(transformedEnv);
    try {
      // The companion keeps the selected target environment. Apply the game
      // override only at final execution, without changing that environment.
      return await originalExec2(
        command,
        args,
        transformGameEnv ? transformGameEnv(transformedEnv) : transformedEnv,
        logPath
      );
    } finally {
      await onExec2?.stop();
    }
  };

  try {
    yield* program();
  } finally {
    wine.exec2 = originalExec2;
  }
}
