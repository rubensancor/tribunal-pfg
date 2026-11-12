// Hook beforePack de electron-builder: deja en build/uv/<os>-<arch>/ el uv de cada plataforma, que la app lleva dentro.
// Para subir de versión, cambia VERSION y los sha256 (https://github.com/astral-sh/uv/releases/download/<v>/<archivo>.sha256).
const { execFileSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const VERSION = "0.13.7";
const ARCHIVOS = { // `${os}-${arch}` de electron-builder → [archivo de la release, sha256]
  "mac-arm64": ["uv-aarch64-apple-darwin.tar.gz", "81b811b57e4624df7ed3aac148e0359100d9962f3d9dce00aec533dc2e086731"],
  "mac-x64": ["uv-x86_64-apple-darwin.tar.gz", "20c47e4c1f630b8abaff8c291fa9b9aa300fef92c4fbff95adf198b55287cda7"],
  "win-x64": ["uv-x86_64-pc-windows-msvc.zip", "0cdc5b38fe5a8168ed6a25814f5ba43c21d313dd3187314fccb37b7cec46e021"],
  "linux-x64": ["uv-x86_64-unknown-linux-musl.tar.gz", "287491da03f2a785c70fa75b13e1f849918c2f2b5415fe84876b8214eeb792f9"],
};
const OS = { darwin: "mac", win32: "win", linux: "linux" };
const ARCH = { 1: "x64", 3: "arm64" }; // el enum Arch de electron-builder

function buscar(dir, nombre) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      const r = buscar(p, nombre);
      if (r) return r;
    } else if (e.name === nombre) return p;
  }
}

exports.default = async function ({ electronPlatformName, arch }) {
  const clave = `${OS[electronPlatformName]}-${ARCH[arch]}`;
  if (!ARCHIVOS[clave]) throw new Error(`No hay uv para ${clave}: añádelo a app/uv.js`);
  const [archivo, sha] = ARCHIVOS[clave];
  const binario = electronPlatformName === "win32" ? "uv.exe" : "uv";
  const destino = path.join(__dirname, "..", "build", "uv", clave);
  const marca = path.join(destino, ".version");
  if (fs.existsSync(marca) && fs.readFileSync(marca, "utf8") === VERSION) return;

  const r = await fetch(`https://github.com/astral-sh/uv/releases/download/${VERSION}/${archivo}`);
  if (!r.ok) throw new Error(`No se ha podido descargar ${archivo}: HTTP ${r.status}`);
  const datos = Buffer.from(await r.arrayBuffer());
  if (crypto.createHash("sha256").update(datos).digest("hex") !== sha) throw new Error(`${archivo} no coincide con su sha256`);

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "uv-"));
  try {
    fs.writeFileSync(path.join(tmp, archivo), datos);
    // shortcut: el tar del sistema; bsdtar (macOS, Windows) abre también el .zip, el GNU tar de Linux no. Basta mientras
    // cada sistema construya su paquete; para construir el de Windows en Linux, usa unzip.
    execFileSync("tar", ["-xf", archivo], { cwd: tmp });
    fs.rmSync(destino, { recursive: true, force: true });
    fs.mkdirSync(destino, { recursive: true });
    fs.copyFileSync(buscar(tmp, binario), path.join(destino, binario));
    fs.chmodSync(path.join(destino, binario), 0o755);
    fs.writeFileSync(marca, VERSION);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
};
