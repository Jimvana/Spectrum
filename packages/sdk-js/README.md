# Spectrum JavaScript SDK

The JavaScript SDK owns the public TypeScript/JavaScript API for embedding Spectrum in apps and tools.

Current package name: `@spectrumstore/sdk`.

The first JavaScript SDK wraps the Spectrum CLI/core command and returns JSON
objects. This keeps the JS API useful while the encoding engine remains Python.

```js
import { SpectrumPack } from "@spectrumstore/sdk";

const pack = await SpectrumPack.create({
  inputPath: "./docs",
  outputPath: "./docs.specpack",
});

console.log(await pack.inspect());
console.log(await pack.verify());
await pack.buildIndex();
console.log(await pack.search("authentication middleware", { topK: 5 }));

const decoded = await pack.unpack("./decoded");
console.log(decoded);
```

By default the SDK runs `spectrum`, matching the root `spectrumstore` npm CLI.
During local development, pass a command
override:

```js
const sdkOptions = {
  command: "python",
  baseArgs: ["-m", "spectrum_cli.main"],
  env: {
    ...process.env,
    PYTHONPATH: "packages/core/src;packages/cli/src;packages/index/src",
  },
};
```

Richer result APIs will be added as the index package matures.
