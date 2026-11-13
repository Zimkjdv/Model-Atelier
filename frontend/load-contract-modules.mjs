import { readFile } from 'node:fs/promises'
import ts from 'typescript'

// List dependencies before their consumers. Resolve only emitted imports so
// type-only imports and ordinary strings do not affect the module graph.
export async function loadContractModules(names) {
  const modules = new Map()
  for (const name of names) {
    const source = await readFile(new URL(`./src/${name}.ts`, import.meta.url), 'utf8')
    let { outputText } = ts.transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    })
    const { importedFiles } = ts.preProcessFile(outputText, true)
    for (const { fileName, pos, end } of importedFiles.reverse()) {
      const url = modules.get(fileName)
      if (!url) throw new Error(`${name}.ts imports ${fileName}; list the dependency first`)
      outputText = outputText.slice(0, pos) + JSON.stringify(url) + outputText.slice(end + 2)
    }
    modules.set(
      `./${name}`,
      'data:text/javascript;base64,' + Buffer.from(outputText).toString('base64'),
    )
  }
  const loaded = []
  for (const [path, url] of modules) loaded.push([path.slice(2), await import(url)])
  return Object.fromEntries(loaded)
}
