const BASE_PATH = "/arni";

export function withBasePath(path: string): string {
  if (!path) return BASE_PATH;
  if (path.startsWith(BASE_PATH)) return path;
  return `${BASE_PATH}${path.startsWith("/") ? path : `/${path}`}`;
}

