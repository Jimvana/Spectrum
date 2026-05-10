export interface SpectrumSdkOptions {
  command?: string;
  baseArgs?: string[];
  env?: NodeJS.ProcessEnv;
}

export interface CreatePackOptions {
  inputPath: string;
  outputPath: string;
  includeAll?: boolean;
  language?: string;
  rle?: "off" | "auto" | "force";
  zlibLevel?: number;
}

export interface DecodedDocument {
  spec_path: string;
  output_path: string;
  dict_version: number;
  original_length: number;
  decoded_length: number;
  token_count: number;
  length_ok: boolean;
  checksum_ok: boolean;
}

export class SpectrumPack {
  readonly path: string;

  constructor(path: string, options?: SpectrumSdkOptions);
  static open(path: string, options?: SpectrumSdkOptions): SpectrumPack;
  static create(options: CreatePackOptions, sdkOptions?: SpectrumSdkOptions): Promise<SpectrumPack>;
  inspect(): Promise<Record<string, unknown>>;
  verify(): Promise<Record<string, unknown>>;
  unpack(outputDir: string): Promise<DecodedDocument[]>;
}

export default SpectrumPack;
