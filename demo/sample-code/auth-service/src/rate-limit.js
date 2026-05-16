const attempts = new Map();

export function recordLoginAttempt(ipAddress) {
  const current = attempts.get(ipAddress) || { count: 0, firstSeen: Date.now() };
  current.count += 1;
  attempts.set(ipAddress, current);
  return current;
}

export function shouldRateLimit(ipAddress, maxAttempts = 5) {
  const current = attempts.get(ipAddress);
  return Boolean(current && current.count >= maxAttempts);
}
