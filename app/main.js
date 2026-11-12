// App de escritorio: arranca el dashboard (dashboard/server.py) con uv y lo muestra en una ventana. Uso: npx electron .
// Empaquetada, el código y uv van en resources/ y el dashboard corre en la carpeta de trabajo, en Documentos.
const { app, BrowserWindow, dialog, shell } = require("electron");
const { execFile, execFileSync, spawn } = require("node:child_process");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");

const REINICIO_APP = 75; // el mismo que server.py: tras actualizarse sale con él y hay que arrancarlo otra vez
const CODIGO = app.isPackaged ? path.join(process.resourcesPath, "tribunal") : path.join(__dirname, "..");
const UV = app.isPackaged ? path.join(process.resourcesPath, "uv", process.platform === "win32" ? "uv.exe" : "uv") : "uv";
let raiz, entorno, servidor, puerto, ventana, saliendo = false;

// Abierta desde Finder o desde el menú de Linux, la app hereda un PATH mínimo: sin el de la shell no encontraría
// uv ni los harnesses (~/.local/bin, Homebrew…), y Ajustes los daría por no instalados.
function pathDeLaShell() {
  if (process.platform === "win32") return process.env.PATH;
  try {
    const salida = execFileSync(process.env.SHELL || os.userInfo().shell || "/bin/sh",
      ["-ilc", 'printf "__PATH__%s__PATH__" "$PATH"'],  // las marcas separan el PATH de lo que imprima el .zshrc
      { encoding: "utf8", timeout: 10000, stdio: ["ignore", "pipe", "ignore"] });
    return salida.match(/__PATH__(.*)__PATH__/)?.[1] || process.env.PATH;
  } catch {
    return process.env.PATH;
  }
}

const puertoLibre = () => new Promise((ok, mal) => {
  const s = net.createServer().once("error", mal).listen(0, "127.0.0.1", () => {
    const { port } = s.address();
    s.close(() => ok(port));
  });
});

const vivo = () => Boolean(servidor?.pid) && servidor.exitCode === null && servidor.signalCode === null;

function fallo(mensaje) {
  if (saliendo) return;
  saliendo = true;
  dialog.showErrorBox("Tribunal PFG", mensaje);
  app.quit();
}

const sinUv = "No se encuentra uv. Instálalo desde https://docs.astral.sh/uv/getting-started/installation/ y vuelve a abrir la app.";

// Copia el código de esta versión a la carpeta de trabajo. Los cambios del docente se conservan y se avisa de ellos.
function instalar() {
  return new Promise(ok => execFile(UV, ["run", path.join(CODIGO, "scripts", "instalar.py"), CODIGO, raiz],
    { env: entorno, encoding: "utf8" }, (e, salida, errores) => {
      if (e) return fallo(e.code === "ENOENT" ? sinUv : `No se ha podido preparar la carpeta ${raiz}.\n\n${errores.trim()}`);
      const { conflictos } = JSON.parse(salida);
      if (conflictos.length) {
        dialog.showMessageBox({
          type: "warning", title: "Tribunal PFG", message: "Se conservan tus cambios",
          detail: `Has cambiado estos archivos de ${raiz} y la versión nueva también los cambia. `
            + `Se quedan los tuyos:\n\n${conflictos.join("\n")}\n\nPara recibir los nuevos, bórralos y vuelve a abrir la app.`,
        });
      }
      ok();
    }));
}

function arrancar(reinicio) {
  let errores = "";
  servidor = spawn(UV, ["run", path.join(raiz, "dashboard", "server.py"), String(puerto)], {
    cwd: raiz,
    env: { ...entorno, TRIBUNAL_APP: "1", ...(reinicio && { TRIBUNAL_REINICIO: "1" }) },
    stdio: ["pipe", "inherit", "pipe"],  // al cerrar su stdin, el servidor para y detiene los agentes en curso
  });
  servidor.stderr.on("data", d => {
    process.stderr.write(d);
    errores = (errores + d).slice(-2000);
  });
  servidor.on("error", e => fallo(e.code === "ENOENT" ? sinUv : `No se ha podido arrancar el dashboard: ${e.message}`));
  servidor.on("exit", codigo => {
    if (saliendo) return app.quit();
    if (codigo === REINICIO_APP) return arrancar(true);  // la página abierta se recarga sola
    fallo(`El dashboard se ha cerrado (código ${codigo}).\n\n${errores.trim()}`);
  });
}

async function esperar(url) {
  while (vivo()) {
    try {
      // Hay que leer el cuerpo: si server.py cierra el socket con él sin leer, undici salta con assert(!this.paused).
      await (await fetch(url)).arrayBuffer();
      return true;
    } catch {
      await new Promise(r => setTimeout(r, 300));
    }
  }
  return false;
}

async function iniciar() {
  const ruta = pathDeLaShell();
  entorno = app.isPackaged
    // El uv de la app va primero, también para los agentes. Solo el Python de uv: en un Mac sin herramientas de
    // desarrollo, /usr/bin/python3 es un aviso que pide instalarlas. Con los certificados del sistema, uv descarga
    // también detrás de un proxy corporativo que inspecciona HTTPS (UV_NATIVE_TLS es el nombre antiguo, ya obsoleto).
    ? {
      ...process.env, PATH: path.dirname(UV) + path.delimiter + ruta,
      UV_PYTHON_PREFERENCE: "only-managed", UV_SYSTEM_CERTS: "1",
    }
    : { ...process.env, PATH: ruta };
  raiz = app.isPackaged ? path.join(app.getPath("documents"), "Tribunal PFG") : CODIGO;
  puerto = await puertoLibre();
  const base = `http://127.0.0.1:${puerto}`;
  ventana = new BrowserWindow({ width: 1400, height: 900, title: "Tribunal PFG" });
  ventana.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(
    '<meta name="color-scheme" content="light dark"><title>Tribunal PFG</title>'
    + '<p style="font:16px system-ui;padding:2em">Arrancando el dashboard… La primera vez tarda un poco.</p>'));
  // Los enlaces externos y el visor de PDF (⌘ o Ctrl más clic) van al navegador del sistema, nunca a esta ventana.
  ventana.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  ventana.webContents.on("will-navigate", (e, url) => {
    if (url.startsWith(base + "/")) return;
    e.preventDefault();
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
  });
  if (app.isPackaged) await instalar();  // si falla, fallo() cierra la app y esta promesa no se resuelve
  arrancar(false);
  if (await esperar(base + "/") && !ventana.isDestroyed()) ventana.loadURL(base + "/");
}

// Una sola instancia: dos servidores sobre la misma carpeta lanzarían dos veces la misma cola.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (ventana?.isMinimized()) ventana.restore();
    ventana?.focus();
  });
  app.whenReady().then(iniciar);
  app.on("window-all-closed", () => app.quit());  // también en macOS: sin ventana no hay quien vea los agentes
  app.on("before-quit", e => {
    if (!vivo()) return;
    e.preventDefault();
    if (servidor.stdin.writableEnded) return;
    saliendo = true;
    servidor.stdin.end();
    setTimeout(() => vivo() && servidor.kill(), 10000);
  });
}
