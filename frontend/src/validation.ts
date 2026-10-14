export function passwordLength(value: string) { return Array.from(value).length }
export function validEmail(value: string) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) }
export function validPassword(value: string) { return passwordLength(value) >= 8 && passwordLength(value) <= 128 }
