import { parse, walk } from 'css-tree'

/** Few correctness checks; Prettier owns layout, and the browser owns the cascade. */
export function lintCss(source) {
  const errors = []
  const report = (rule, node) =>
    errors.push(`${rule} at ${node.loc?.start.line || 1}:${node.loc?.start.column || 1}`)
  let ast
  try {
    ast = parse(source, {
      positions: true,
      onParseError: (error) => errors.push(`syntax: ${error.message}`),
    })
  } catch (error) {
    return [`syntax: ${error.message}`]
  }
  walk(ast, {
    enter(node) {
      if (node.type === 'Block') {
        const properties = new Set()
        node.children.forEach((child) => {
          if (child.type !== 'Declaration') return
          const property = child.property.startsWith('--')
            ? child.property
            : child.property.toLowerCase()
          if (properties.has(property)) report('duplicate-property ' + property, child)
          properties.add(property)
        })
      }
      if (
        node.type === 'Hash' &&
        !/^(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(node.value)
      ) {
        report('invalid-hex-color', node)
      }
    },
  })
  return errors
}
