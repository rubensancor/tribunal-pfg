// Empaqueta la app de escritorio. Uso: npm run dist (para la plataforma actual) o npx electron-builder --config
// app/electron-builder.config.js --mac --win --linux. Los paquetes salen en dist/.
const fs = require("node:fs");
const path = require("node:path");

const SKILLS = "{leer,grado,preguntas,anotaciones}-pfg"; // las del docente; verify-tribunal es de desarrollo

module.exports = {
  appId: "io.github.rubensancor.tribunal-pfg",
  productName: "Tribunal PFG",
  extraMetadata: { version: fs.readFileSync(path.join(__dirname, "..", "VERSION"), "utf8").trim() },
  artifactName: "Tribunal-PFG-${version}-${os}-${arch}.${ext}", // sin espacios: GitHub los cambiaría por puntos
  files: ["app/main.js", "package.json"],
  // El código que corre en la carpeta de trabajo: lo que necesitan el dashboard y los agentes, nada de desarrollo.
  extraResources: [
    {
      from: ".", to: "tribunal", filter: [
        "AGENTS.md", "CLAUDE.md", "VERSION", "LICENSE", ".agents/agents/**", `.agents/skills/${SKILLS}/**`,
        ".codex/**", ".opencode/**", "config/categorias.json", "dashboard/**", "scripts/**", "!**/__pycache__",
      ],
    },
    // .claude/ son enlaces a .agents/ en el repo; aquí van como carpetas, que el instalador de Windows no lleva enlaces.
    { from: ".agents/agents", to: "tribunal/.claude/agents" },
    { from: ".agents/skills", to: "tribunal/.claude/skills", filter: [`${SKILLS}/**`] },
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
