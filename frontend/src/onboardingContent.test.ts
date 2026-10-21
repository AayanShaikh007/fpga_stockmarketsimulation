import { describe, expect, it } from 'vitest'
import { GUIDE_VERSION, rememberGuide, shouldShowGuide } from './onboardingContent'

describe('versioned introduction preferences', () => {
  it('shows on first visit and remembers closing for this version', () => {
    const values = new Map<string,string>()
    const storage = { getItem: (key:string) => values.get(key) ?? null, setItem: (key:string,value:string) => { values.set(key,value) } }
    expect(shouldShowGuide(storage)).toBe(true)
    rememberGuide(storage)
    expect([...values.values()]).toEqual([GUIDE_VERSION])
    expect(shouldShowGuide(storage)).toBe(false)
  })
  it('shows revised content after a version change', () => {
    expect(shouldShowGuide({ getItem: () => 'older-version', setItem: () => {} })).toBe(true)
  })
  it('works when browser persistence is unavailable', () => {
    const blocked = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } }
    expect(shouldShowGuide(blocked)).toBe(true)
    expect(() => rememberGuide(blocked)).not.toThrow()
    expect(shouldShowGuide(null)).toBe(true)
  })
})
