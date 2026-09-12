import archive from "../../sidecar/native-fullscreen/payload.tar.gz?url";
import checksum from "../../sidecar/native-fullscreen/payload.sha256?url";
import compatible from "../../sidecar/native-fullscreen/compatible-ntdll.txt?url";
import idle from "../../sidecar/native-fullscreen/check-idle?url";
import installer from "../../sidecar/native-fullscreen/install-support.sh?url";
import payloadChecksum from "../../sidecar/native-fullscreen/payload.sha256?raw";
import { exec, mkdirp, readFile, resolve, writeBinary } from "@utils";

export const NATIVE_FULLSCREEN_PAYLOAD_CHECKSUM = payloadChecksum;

export async function nativeFullscreenSupportDirectory() {
  const bundled = resolve("./sidecar/native-fullscreen");
  try {
    if ((await readFile(`${bundled}/payload.sha256`)) === payloadChecksum)
      return bundled;
  } catch {
    // A resources.neu-only launcher update may not include a new sidecar tree.
  }
  // Include the same signed payload in the web resource archive as well as full
  // app packages. Materialize it locally without an external download/build.
  const directory = resolve(
    `./native-fullscreen-support/${payloadChecksum.slice(0, 64)}`
  );
  await mkdirp(directory);
  for (const [name, url] of Object.entries({
    "payload.tar.gz": archive,
    "payload.sha256": checksum,
    "compatible-ntdll.txt": compatible,
    "check-idle": idle,
    "install-support.sh": installer,
  })) {
    const response = await fetch(url);
    if (!response.ok)
      throw new Error("Could not read bundled Native Fullscreen support.");
    await writeBinary(`${directory}/${name}`, await response.arrayBuffer());
  }
  await exec(["chmod", "755", `${directory}/check-idle`]);
  await exec(["codesign", "--verify", "--strict", `${directory}/check-idle`]);
  return directory;
}
