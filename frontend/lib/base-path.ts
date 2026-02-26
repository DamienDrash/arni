const BASE_PATH = "";

export function withBasePath(path: string): string {
  if (!path) return "/";
  if (BASE_PATH && path.startsWith(BASE_PATH)) return path;
  return BASE_PATH ? `${BASE_PATH}${path.startsWith("/") ? path : `/${path}`}` : path;
}
