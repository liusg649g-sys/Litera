import { describe, expect, it } from 'vitest'
import { validEmail, validPassword, passwordLength } from '../src/validation'
describe('registration field validation', () => {
  it('rejects malformed email', () => {
    expect(validEmail('jensen@example.com')).toBe(true)
    for (const email of ['', 'a', 'a@', '@example.com', 'a b@example.com']) expect(validEmail(email)).toBe(false)
  })
  it('counts unicode password characters consistently with backend', () => {
    expect(passwordLength('😀'.repeat(8))).toBe(8)
    expect(validPassword('😀'.repeat(8))).toBe(true)
    expect(validPassword('a'.repeat(7))).toBe(false)
    expect(validPassword('a'.repeat(129))).toBe(false)
  })
})
