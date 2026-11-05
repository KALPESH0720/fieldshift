/*
 * FieldShift frontend: Shared API Client
 * Feature: Centralizes HTTP requests, shared headers, timeout behavior, and consistent error handling for backend communication.
 * Impact: It reduces duplicate request logic and keeps API calls predictable across feature modules.
 * Importance: This improves reliability when the app grows and makes debugging and future backend upgrades easier.
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '');
const DEFAULT_TIMEOUT_MS = 15000;
const DEVICE_ID_KEY = 'fieldshift-device-id';

let csrfTokenMemory = null;
let refreshPromise = null;

export class ApiClientError extends Error {
  constructor({
    message = 'Request failed',
    code = 'server_error',
    status = 500,
    retryAfterSeconds = null,
    details = null,
    requestId = null,
  } = {}) {
    super(message);
    this.name = 'ApiClientError';
    this.code = code;
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
    this.details = details;
    this.requestId = requestId;
  }
}

export function setCsrfToken(token) {
  csrfTokenMemory = token || null;
}

export function getCsrfToken() {
  return csrfTokenMemory;
}

export function getDeviceId() {
  if (typeof window === 'undefined') return 'server-device';
  try {
    let id = window.localStorage.getItem(DEVICE_ID_KEY);
    if (!id) {
      id = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : `fs-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem(DEVICE_ID_KEY, id);
    }
    return id;
  } catch {
    return 'ephemeral-device';
  }
}

function generateRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

async function parseErrorResponse(response) {
  const retryHeader = response.headers?.get?.('Retry-After');
  const parsedRetryHeader = retryHeader && Number.isFinite(Number(retryHeader))
    ? Number(retryHeader)
    : null;

  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  const envelope = payload?.error || payload || {};
  const retryAfterSeconds = envelope.retryAfterSeconds ?? parsedRetryHeader ?? null;

  let fallbackCode = 'server_error';
  if (response.status === 401) fallbackCode = 'unauthenticated';
  else if (response.status === 410) fallbackCode = 'otp_expired';
  else if (response.status === 429) fallbackCode = 'rate_limited';
  else if (response.status === 400 || response.status === 422) fallbackCode = 'validation_error';

  return new ApiClientError({
    message: envelope.message || response.statusText || 'Request failed',
    code: envelope.code || fallbackCode,
    status: response.status,
    retryAfterSeconds,
    details: envelope.details || null,
    requestId: envelope.requestId || null,
  });
}

export async function apiRequest(
  path,
  {
    method = 'GET',
    body = undefined,
    headers = {},
    timeoutMs = DEFAULT_TIMEOUT_MS,
    skipAuthRefresh = false,
  } = {},
) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    throw new ApiClientError({
      message: 'No internet connection',
      code: 'network',
      status: 0,
    });
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${API_BASE_URL}${normalizedPath}`;
  const upperMethod = method.toUpperCase();
  const isMutating = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(upperMethod);

  const requestHeaders = {
    Accept: 'application/json',
    'X-Device-Id': getDeviceId(),
    'X-Request-Id': generateRequestId(),
    ...headers,
  };

  if (body !== undefined && !(body instanceof FormData)) {
    requestHeaders['Content-Type'] = 'application/json';
  }

  if (isMutating && csrfTokenMemory) {
    requestHeaders['X-CSRF-Token'] = csrfTokenMemory;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs);

  try {
    const response = await fetch(url, {
      method: upperMethod,
      headers: requestHeaders,
      body: body === undefined
        ? undefined
        : body instanceof FormData
        ? body
        : JSON.stringify(body),
      credentials: 'include',
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (
      response.status === 401 &&
      !skipAuthRefresh &&
      !normalizedPath.startsWith('/auth/otp/') &&
      normalizedPath !== '/auth/refresh' &&
      normalizedPath !== '/auth/logout'
    ) {
      const refreshed = await attemptTokenRefresh();
      if (refreshed) {
        return apiRequest(path, {
          method,
          body,
          headers,
          timeoutMs,
          skipAuthRefresh: true,
        });
      }
    }

    if (!response.ok) {
      throw await parseErrorResponse(response);
    }

    if (response.status === 204) {
      return null;
    }

    const contentType = response.headers?.get?.('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await response.json();
      if (data?.csrfToken) {
        setCsrfToken(data.csrfToken);
      }
      return data;
    }

    return null;
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof ApiClientError) {
      throw error;
    }

    if (
      error?.name === 'TimeoutError' ||
      error?.name === 'AbortError' ||
      String(error?.message || '').toLowerCase().includes('timed out')
    ) {
      throw new ApiClientError({
        message: 'Request timed out',
        code: 'timeout',
        status: 408,
      });
    }

    throw new ApiClientError({
      message: error?.message || 'Network error',
      code: 'network',
      status: 0,
    });
  }
}

async function attemptTokenRefresh() {
  if (!refreshPromise) {
    refreshPromise = apiRequest('/auth/refresh', {
      method: 'POST',
      skipAuthRefresh: true,
    })
      .then((data) => {
        if (data?.csrfToken) {
          setCsrfToken(data.csrfToken);
        }
        return Boolean(data?.user);
      })
      .catch(() => {
        setCsrfToken(null);
        return false;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}
