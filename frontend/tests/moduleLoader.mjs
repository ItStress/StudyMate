import { access, readFile } from 'node:fs/promises'
import vm from 'node:vm'
import ts from 'typescript'

// Resolve real local modules while keeping external dependencies replaceable.
export function createModuleLoader(globals = {}, imports = {}) {
  const context = vm.createContext(globals)
  const modules = new Map()

  function external(specifier, exports) {
    if (!modules.has(specifier)) {
      modules.set(specifier, new vm.SyntheticModule(Object.keys(exports), function () {
        for (const [name, value] of Object.entries(exports)) this.setExport(name, value)
      }, { context }))
    }
    return modules.get(specifier)
  }

  async function resolve(specifier, parent) {
    for (const suffix of ['', '.ts', '.tsx']) {
      const url = new URL(`${specifier}${suffix}`, parent)
      try {
        await access(url)
        return url
      } catch {
        // Try the next TypeScript extension.
      }
    }
    throw new Error(`Cannot resolve ${specifier} from ${parent}`)
  }

  async function loadModule(url) {
    if (modules.has(url.href)) return modules.get(url.href)
    const source = await readFile(url, 'utf8')
    const { outputText } = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
    })
    const module = new vm.SourceTextModule(outputText, { context })
    modules.set(url.href, module)
    await module.link(async (specifier) => {
      if (Object.hasOwn(imports, specifier)) return external(specifier, imports[specifier])
      if (specifier.startsWith('.')) {
        // Styles have no behavior in the Node rendering harness.
        if (specifier.endsWith('.css')) return external(specifier, {})
        return loadModule(await resolve(specifier, url))
      }
      return external(specifier, await import(specifier))
    })
    return module
  }

  return loadModule
}
