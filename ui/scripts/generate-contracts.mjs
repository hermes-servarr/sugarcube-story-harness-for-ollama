import { mkdir, readFile, writeFile } from "node:fs/promises";
import process from "node:process";
import openapiTS, { astToString } from "openapi-typescript";

const check = process.argv.includes("--check");
const schemaUrl = new URL("../openapi.json", import.meta.url);
const outputUrl = new URL("../src/generated/openapi.ts", import.meta.url);
const schema = JSON.parse(await readFile(schemaUrl, "utf8"));
const generated = `${astToString(await openapiTS(schema))}`;

if (check) {
  const current = await readFile(outputUrl, "utf8").catch(() => "");
  if (current !== generated) {
    throw new Error("src/generated/openapi.ts is stale; run npm run contracts:generate");
  }
} else {
  await mkdir(new URL("../src/generated/", import.meta.url), { recursive: true });
  await writeFile(outputUrl, generated, "utf8");
}
