import { createClient as createGenshinCnClient } from "../clients/hk4ecn";
import type { HoyoplayGameSpec } from "./hoyoplay";

export const HOYOPLAY_CN_GAME_SPECS: HoyoplayGameSpec[] = [
  {
    id: "genshin",
    namespace: "hpcngenshin",
    title: "Genshin Impact CN",
    fpsSupported: true,
    createClient: createGenshinCnClient,
  },
];
