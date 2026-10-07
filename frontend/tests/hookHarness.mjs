// Minimal hook lifecycle harness with dependency-aware effects and cleanup.
export function createHookHarness() {
  const cells = []
  let cursor = 0
  let effects = []
  const react = {
    useState(initial) {
      const index = cursor++
      if (!(index in cells)) cells[index] = { value: typeof initial === 'function' ? initial() : initial }
      return [cells[index].value, (value) => {
        cells[index].value = typeof value === 'function' ? value(cells[index].value) : value
      }]
    },
    useRef(initial) {
      const index = cursor++
      if (!(index in cells)) cells[index] = { current: initial }
      return cells[index]
    },
    useEffect(effect, dependencies) {
      const index = cursor++
      const previous = cells[index]
      if (!previous || !dependencies || dependencies.some((value, i) => !Object.is(value, previous.dependencies[i]))) {
        effects.push(() => {
          previous?.cleanup?.()
          cells[index] = { dependencies, cleanup: effect() }
        })
      }
    },
  }
  return {
    react,
    render(hook, ...args) {
      cursor = 0
      const result = hook(...args)
      const pending = effects
      effects = []
      for (const effect of pending) effect()
      return result
    },
    unmount() { for (const cell of cells) cell?.cleanup?.() },
  }
}

export function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

export async function settle() {
  await new Promise((resolve) => setImmediate(resolve))
}
