const sessions = new Map();

export function createBearerToken(userId) {
  const token = `token-${userId}-${Date.now()}`;
  sessions.set(token, { userId, createdAt: Date.now() });
  return token;
}

export function authenticationMiddleware(request, response, next) {
  const header = request.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice("Bearer ".length) : "";

  if (!sessions.has(token)) {
    response.statusCode = 401;
    response.end("missing or invalid bearer token");
    return;
  }

  request.user = sessions.get(token);
  next();
}

export function revokeToken(token) {
  return sessions.delete(token);
}
