export const MIN_FPS_TARGET = 1;
export const MAX_FPS_TARGET = 360;
export const FPS_TARGET_ERROR = `Target FPS must be a whole number from ${MIN_FPS_TARGET} to ${MAX_FPS_TARGET}. Choose a valid target before saving or launching with FPS unlocking enabled.`;

export function getFpsTargetError(value: string | number) {
  const target = Number(value);
  return (typeof value === "string" && value.trim() === "") ||
    !Number.isInteger(target) ||
    target < MIN_FPS_TARGET ||
    target > MAX_FPS_TARGET
    ? FPS_TARGET_ERROR
    : undefined;
}

export function resolveFpsTarget(value: string | number) {
  const error = getFpsTargetError(value);
  if (error) throw new Error(error);
  return Number(value);
}
