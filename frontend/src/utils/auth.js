/**
 * @file auth.js
 * @description Token validation helpers used by streaming endpoints
 *              that need to inject a JWT into the WebSocket URL.
 */

export function getValidAccessToken() {
  const token = localStorage.getItem('access_token')
  if (!token) return null

  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (!payload?.exp) return token
    const now = Math.floor(Date.now() / 1000)
    if (payload.exp <= now) return null
    return token
  } catch {
    return null
  }
}
