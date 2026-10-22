import assert from 'node:assert/strict'
import { lintCss } from './css-checks.mjs'

assert.deepEqual(
  lintCss('a{color:#abc;--Tone:1;--tone:2} @media(min-width:10px){a{color:#12345678}}'),
  [],
)
assert(lintCss('a{color:#12zzzz}').some((value) => value.startsWith('invalid-hex-color')))
assert(lintCss('a{COLOR:red;color:blue}').some((value) => value.startsWith('duplicate-property')))
assert(lintCss('a{--tone:red;--tone:blue}').some((value) => value.startsWith('duplicate-property')))
assert(lintCss('a{color:red;???}').some((value) => value.startsWith('syntax')))
assert.deepEqual(lintCss('a{color:red}a{color:blue}'), [])
console.log(
  'CSS syntax, duplicate declaration, custom-property case and invalid hex probes passed.',
)
