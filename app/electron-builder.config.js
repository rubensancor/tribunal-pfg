// Empaqueta la app de escritorio. Uso: npm run dist (para la plataforma actual) o npx electron-builder --config
// app/electron-builder.config.js --mac --win --linux. Los paquetes salen en dist/.
const fs = require("node:fs");
const path = require("node:path");

const RAIZ = path.join(__dirname, "..");
// El código que corre en la carpeta de trabajo: lo que necesitan el dashboard y los agentes, nada de desarrollo.
// Es la misma lista con la que el botón Actualizar saca el código del tarball de la release.
const CODIGO = JSON.parse(fs.readFileSync(path.join(RAIZ, "scripts", "codigo.json"), "utf8"));

module.exports = {
  appId: "io.github.rubensancor.tribunal-pfg",
  productName: "Tribunal PFG",
  icon: "app/icon.png", // 1024 px; de él salen el .icns de macOS y el .ico de Windows. Fuente: app/icon.svg
  extraMetadata: { version: fs.readFileSync(path.join(RAIZ, "VERSION"), "utf8").trim() },
  artifactName: "Tribunal-PFG-${version}-${os}-${arch}.${ext}", // sin espacios: GitHub los cambiaría por puntos
  files: ["app/main.js", "package.json"],
  extraResources: [
    {
      from: ".", to: "tribunal",
      filter: [...CODIGO.map(p => fs.statSync(path.join(RAIZ, p)).isDirectory() ? `${p}/**` : p), "!**/__pycache__"],
    },
    // .claude/ son enlaces a .agents/ en el repo; aquí van como carpetas, que el instalador de Windows no lleva enlaces.
    ...CODIGO.filter(p => p.startsWith(".agents/")).map(p => ({ from: p, to: "tribunal/.claude/" + p.slice(8) })),
    { from: "build/uv/${os}-${arch}", to: "uv", filter: ["uv", "uv.exe"] },
  ],
  beforePack: "app/uv.js",
  mac: {
    target: [{ target: "dmg", arch: ["arm64", "x64"] }],
    category: "public.app-category.education",
    identity: "-", // firma ad hoc, sin Apple Developer: en Apple Silicon una app sin ninguna firma no arranca
    hardenedRuntime: false, // solo lo pide la notarización; con firma ad hoc impediría cargar las librerías de Electron
  },
  win: { target: [{ target: "nsis", arch: ["x64"] }] },
  linux: { target: [{ target: "AppImage", arch: ["x64"] }], category: "Education" },
};
