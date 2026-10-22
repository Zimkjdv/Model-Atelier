import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import * as prettier from 'prettier'
import { lintCss } from './css-checks.mjs'

const root = fileURLToPath(new URL('../', import.meta.url))
const scope = JSON.parse(await readFile(path.join(root, 'quality-scope.json'), 'utf8'))
const mode = process.argv[2]
if (mode === 'lint') {
  for (const name of scope.css) {
    const errors = lintCss(await readFile(path.join(root, name), 'utf8'))
    for (const error of errors) console.error(`${name}: ${error}`)
    if (errors.length) process.exitCode = 1
  }
} else if (['--write', '--check'].includes(mode)) {
  for (const name of scope.web) {
    const file = path.join(root, name)
    const source = await readFile(file, 'utf8')
    const options = { ...(await prettier.resolveConfig(file)), filepath: file }
    const formatted = await prettier.format(source, options)
    if (source === formatted) continue
    if (mode === '--write') {
      await writeFile(file, formatted, 'utf8')
      console.log('Formatted: ' + name)
    } else {
      console.error('Needs formatting: ' + name)
      process.exitCode = 1
    }
  }
} else {
  console.error('Usage: node check-style.mjs --check | --write | lint')
  process.exitCode = 2
}
