import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export class SpectrumPack {
  constructor(path, options = {}) {
    this.path = path;
    this.command = options.command || process.env.SPECTRUM_COMMAND || "spectrum-core";
    this.baseArgs = options.baseArgs || [];
    this.env = options.env || process.env;
  }

  static open(path, options = {}) {
    return new SpectrumPack(path, options);
  }

  static async create({ inputPath, outputPath, includeAll = false, language, rle = "off", zlibLevel = 9 }, options = {}) {
    const pack = new SpectrumPack(outputPath, options);
    const args = ["pack", inputPath, outputPath, "--rle", rle, "--zlib-level", String(zlibLevel), "--json"];
    if (includeAll) args.push("--all");
    if (language) args.push("--language", language);
    await pack._run(args);
    return pack;
  }

  async inspect() {
    return this._run(["inspect", this.path, "--json"]);
  }

  async verify() {
    return this._run(["verify", this.path, "--json"]);
  }

  async buildIndex({ embed = true, outputPath } = {}) {
    const args = ["index", this.path, "--json"];
    if (embed) args.push("--embed");
    if (outputPath) args.push("--output", outputPath);
    return this._run(args);
  }

  async search(query, { topK = 10, language = "txt", indexPath, buildIfMissing = true } = {}) {
    const args = ["search", this.path, query, "--top", String(topK), "--language", language, "--json"];
    if (indexPath) args.push("--index", indexPath);
    if (!buildIfMissing) args.push("--no-build");
    return this._run(args);
  }

  async unpack(outputDir) {
    return this._run(["unpack", this.path, outputDir, "--json"]);
  }

  async _run(args) {
    const { stdout } = await execFileAsync(
      this.command,
      [...this.baseArgs, ...args],
      {
        env: this.env,
        maxBuffer: 20 * 1024 * 1024,
        windowsHide: true,
      },
    );
    return JSON.parse(stdout);
  }
}

export default SpectrumPack;
