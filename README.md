# YAAGL — Genshin launcher for macOS

This fork of [YAAGL](https://github.com/rishabhroyy/yet-another-anime-game-launcher) provides a compact Genshin-focused HoYoPlay interface, regional distribution choices, game installation and updates, and per-game Wine and renderer settings. HSR and ZZZ support is removed from this fork.

## Features

- Integer FPS targets from 1 through 360, with a default of 120 and an option to disable unlocking.
- Saved settings remain selected across launches. Targets above 60 use the FPS companion automatically; the game and companion receive their respective DXMT settings.
- Launch ownership prevents overlapping launches and keeps cleanup running before normal launcher shutdown.
- Per-game Wine selection and prefixes, with request-scoped Wine shutdown waiting.

An FPS target is a requested limit, not a guarantee of rendered performance. Actual frame rates depend on the game, renderer and hardware. Wine and the FPS companion are distributed separately; building this launcher does not build or patch Wine.

## Installation

Use an application package from this fork's [releases](https://github.com/zh0ngy1l1/yet-another-anime-game-launcher/releases), when available, or build from source. Move the application to `/Applications` before opening it. Keep game files in a writable directory in your home folder rather than inside `/Applications`.

## Development

Use Node.js, pnpm, Python and uv. The Sophon helper build also needs the macOS compiler tools. Install dependencies and prepare the native support files:

```sh
pnpm install
./configure.sh
./build-sophon.sh
```

Run the Genshin HoYoPlay development build:

```sh
pnpm run start-hoyoplay
```

Check the source and build the frontend without launching the application:

```sh
pnpm run typecheck
pnpm run lint
pnpm test
pnpm run build-hoyoplay
```

Package the application after building Sophon:

```sh
YAAGL_CHANNEL_CLIENT=hoyoplay node build-app.js
```

Use `hoyoplaycn` for the Chinese distribution.

## Related projects

- [Neutralinojs](https://github.com/3Shain/neutralinojs)
- [DXMT](https://github.com/3Shain/dxmt)
- [YAAGL Wine](https://github.com/yaagl/anime-game-wine)

## License

See [LICENSE](LICENSE). Thanks to the upstream YAAGL contributors, An Anime Team, Krock and mkrsym1.
