import { spawn } from "node:child_process";
import { resolve } from "node:path";

const task = process.argv[2] || "assembleDebug";
const androidDir = resolve(import.meta.dirname, "..", "android");
const command = process.platform === "win32" ? "gradlew.bat" : "./gradlew";
const child = spawn(command, [task], { cwd: androidDir, stdio: "inherit", shell: process.platform === "win32" });
child.on("exit", (code) => process.exit(code ?? 1));
