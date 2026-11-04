/**
 * API client wrapper for DARKTRACE backend services.
 * Enforces standard response envelope parsing:
 *   { success: boolean, data: any, error: { code, message, details }, meta: object }
 * Automatically attaches Authorization header and handles session invalidation.
 */

const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl) {
    return envUrl.replace('localhost', '127.0.0.1');
  }
  return 'http://127.0.0.1:8000/api/v1';
};

const API_BASE_URL = getApiBaseUrl();

export const TOKEN_KEY = 'darktrace_token';
export const USER_KEY = 'darktrace_user';
export const NOTICE_KEY = 'darktrace_session_notice';

const SESSION_EXPIRED_CODES = new Set([
  'TOKEN_EXPIRED',
  'TOKEN_INVALID',
  'NOT_AUTHENTICATED',
  'ACCOUNT_DISABLED',
]);

/**
 * Standard fetch wrapper that handles authentication, query parameters, network errors,
 * and JSON envelope parsing.
 *
 * @param {string} endpoint - API path relative to base URL (e.g. '/investigations')
 * @param {RequestInit & { params?: Record<string, any>, includeMeta?: boolean }} [options={}]
 * @returns {Promise<any>}
 */
export async function apiRequest(endpoint, options = {}) {
  let url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  // 1. Serialize query parameters if present
  if (options.params && typeof options.params === 'object') {
    const searchParams = new URLSearchParams();
    Object.entries(options.params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        searchParams.append(key, String(val));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  // 2. Prepare request headers and attach token if available
  const headers = {
    ...(options.headers || {}),
  };

  // Only set default Content-Type to application/json if not sending FormData
  if (!(options.body instanceof FormData) && !headers['Content-Type'] && !headers['content-type']) {
    headers['Content-Type'] = 'application/json';
  }

  const storedToken = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(TOKEN_KEY) : null;
  if (storedToken && !headers.Authorization && !headers.authorization) {
    headers.Authorization = `Bearer ${storedToken}`;
  }

  // 3. Automatically stringify JSON body if needed
  let body = options.body;
  if (body && typeof body === 'object' && !(body instanceof FormData) && !(body instanceof Blob)) {
    body = JSON.stringify(body);
  }

  // 4. Execute fetch
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      body,
    });
  } catch (netErr) {
    const errorObj = new Error(`Backend unreachable: Could not connect to API server at ${url}.`);
    errorObj.code = 'BACKEND_UNREACHABLE';
    errorObj.details = netErr.message;
    throw errorObj;
  }

  // 5. Parse response JSON
  let parsedJson;
  try {
    parsedJson = await response.json();
  } catch (parseErr) {
    const errorObj = new Error(`Invalid response format from server (HTTP ${response.status}).`);
    errorObj.code = 'INVALID_RESPONSE';
    errorObj.status = response.status;
    throw errorObj;
  }

  // 6. Handle standard DARKTRACE envelope
  if (parsedJson && typeof parsedJson === 'object') {
    if (parsedJson.success === true) {
      if (options.includeMeta) {
        return { data: parsedJson.data, meta: parsedJson.meta || {} };
      }
      return parsedJson.data;
    }

    if (parsedJson.success === false && parsedJson.error) {
      const errCode = parsedJson.error.code || 'API_ERROR';
      const errMsg = parsedJson.error.message || 'API request returned unsuccessful status';
      const errorObj = new Error(errMsg);
      errorObj.code = errCode;
      errorObj.details = parsedJson.error.details;
      errorObj.status = response.status;

      // Handle session expiry on 401 for authenticated requests (exclude /auth/login)
      if (response.status === 401 && SESSION_EXPIRED_CODES.has(errCode) && !endpoint.includes('/auth/login')) {
        if (typeof sessionStorage !== 'undefined') {
          sessionStorage.removeItem(TOKEN_KEY);
          sessionStorage.removeItem(USER_KEY);
          sessionStorage.setItem(NOTICE_KEY, 'Your session expired. Please sign in again.');
        }
        if (typeof window !== 'undefined' && window.location && window.location.pathname !== '/login') {
          // Trigger redirect
          window.location.href = '/login';
        }
      }

      throw errorObj;
    }
  }

  const fallbackErr = new Error(`Unexpected response envelope from ${url} (HTTP ${response.status}).`);
  fallbackErr.code = 'UNEXPECTED_ENVELOPE';
  throw fallbackErr;
}

// =====================================================================
// Endpoint Helpers
// =====================================================================

export async function loginApi(identifier, password) {
  return apiRequest('/auth/login', {
    method: 'POST',
    body: { identifier, password },
  });
}

export async function fetchMeApi() {
  return apiRequest('/auth/me');
}

export async function changePasswordApi(current_password, new_password) {
  return apiRequest('/auth/change-password', {
    method: 'POST',
    body: { current_password, new_password },
  });
}

export async function fetchDashboardSummary() {
  return apiRequest('/dashboard/summary');
}

export async function fetchInvestigations(params = {}) {
  return apiRequest('/investigations', {
    method: 'GET',
    params,
    includeMeta: true,
  });
}

export async function fetchInvestigationById(id) {
  return apiRequest(`/investigations/${id}`);
}

export async function createInvestigationApi(payload) {
  return apiRequest('/investigations', {
    method: 'POST',
    body: payload,
  });
}

export async function fetchUsers(params = {}) {
  return apiRequest('/users', {
    method: 'GET',
    params,
    includeMeta: true,
  });
}

export async function createUserApi(payload) {
  return apiRequest('/users', {
    method: 'POST',
    body: payload,
  });
}

export async function updateUserApi(id, payload) {
  return apiRequest(`/users/${id}`, {
    method: 'PATCH',
    body: payload,
  });
}

export async function resetUserPasswordApi(id, password) {
  return apiRequest(`/users/${id}/reset-password`, {
    method: 'POST',
    body: { password },
  });
}

export async function fetchHealth() {
  return apiRequest('/health');
}

export async function fetchSystemInfo() {
  return apiRequest('/system/info');
}

// =====================================================================
// Phase 5: Datasets & Ingestion Endpoints
// =====================================================================

export async function fetchSampleDatasets() {
  return apiRequest('/datasets/samples');
}

export async function loadSampleDatasetApi(investigationId, key) {
  return apiRequest(`/investigations/${investigationId}/datasets/samples/${key}`, {
    method: 'POST',
  });
}

export async function previewManualPostApi(investigationId, payload) {
  return apiRequest(`/investigations/${investigationId}/ingest/manual/preview`, {
    method: 'POST',
    body: payload,
  });
}

export async function commitManualPostApi(investigationId, payload) {
  return apiRequest(`/investigations/${investigationId}/ingest/manual/commit`, {
    method: 'POST',
    body: payload,
  });
}

export async function previewFileUploadApi(investigationId, formData) {
  return apiRequest(`/investigations/${investigationId}/ingest/file/preview`, {
    method: 'POST',
    body: formData,
  });
}

export async function commitFileUploadApi(investigationId, formData) {
  return apiRequest(`/investigations/${investigationId}/ingest/file/commit`, {
    method: 'POST',
    body: formData,
  });
}

export async function fetchInvestigationPosts(investigationId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/posts`, {
    method: 'GET',
    params,
    includeMeta: true,
  });
}

export async function fetchInvestigationDatasets(investigationId) {
  return apiRequest(`/investigations/${investigationId}/datasets`);
}

// =====================================================================
// Phase 6: Post Extraction & Indicator Analytics Endpoints
// =====================================================================

export async function previewExtractionApi(content, structured_indicators = null) {
  return apiRequest('/extraction/preview', {
    method: 'POST',
    body: {
      content,
      structured_indicators,
    },
  });
}

export async function rerunInvestigationExtractionApi(investigationId, force = false) {
  return apiRequest(`/investigations/${investigationId}/extraction/rerun`, {
    method: 'POST',
    body: { force },
  });
}

export async function fetchInvestigationIndicators(investigationId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/indicators`, {
    method: 'GET',
    params,
    includeMeta: true,
  });
}

export async function fetchInvestigationIndicatorsSummary(investigationId) {
  return apiRequest(`/investigations/${investigationId}/indicators/summary`);
}

export async function fetchInvestigationPostDetail(investigationId, postId) {
  return apiRequest(`/investigations/${investigationId}/posts/${postId}`);
}

// =====================================================================
// Phase 7: Pipeline Runs & Correlation Evidence Endpoints
// =====================================================================

export async function fetchPipelineStages() {
  return apiRequest('/pipeline/stages');
}

export async function triggerPipelineRun(investigationId, stages = null) {
  return apiRequest(`/investigations/${investigationId}/pipeline/runs`, {
    method: 'POST',
    body: stages ? { stages } : {},
  });
}

export async function fetchPipelineRuns(investigationId) {
  return apiRequest(`/investigations/${investigationId}/pipeline/runs`);
}

export async function fetchPipelineRunDetail(investigationId, runId) {
  return apiRequest(`/investigations/${investigationId}/pipeline/runs/${runId}`);
}

export async function fetchInvestigationEvidence(investigationId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/evidence`, {
    method: 'GET',
    params,
    includeMeta: true,
  });
}

export async function fetchInvestigationEvidenceDetail(investigationId, evidenceId) {
  return apiRequest(`/investigations/${investigationId}/evidence/${evidenceId}`);
}

export async function fetchInvestigationPairs(investigationId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/pairs`, {
    method: 'GET',
    params,
    includeMeta: true,
  });
}

export async function fetchActiveScoringConfig() {
  return apiRequest('/scoring-configs/active');
}

// =====================================================================
// Phase 8: Correlation & Stylometry Endpoints
// =====================================================================

export async function fetchInvestigationCorrelations(investigationId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/correlations`, {
    method: 'GET',
    params,
    includeMeta: true,
  });
}

export async function fetchCorrelationDetail(investigationId, actorA, actorB, runId = null) {
  const params = runId ? { run_id: runId } : {};
  return apiRequest(`/investigations/${investigationId}/correlations/${actorA}/${actorB}`, {
    method: 'GET',
    params,
  });
}

export async function fetchAnalysisActors(investigationId, runId = null) {
  const params = runId ? { run_id: runId } : {};
  return apiRequest(`/investigations/${investigationId}/analysis/actors`, {
    method: 'GET',
    params,
  });
}

export async function compareStylometryTextApi(textA, textB, authorA = 'Sample A', authorB = 'Sample B') {
  return apiRequest('/stylometry/compare', {
    method: 'POST',
    body: {
      text_a: textA,
      text_b: textB,
      author_a: authorA,
      author_b: authorB,
    },
  });
}

// =====================================================================
// Phase 9: Workspace, Graph, Chronology, Actor Profile & Dossier Endpoints
// =====================================================================

export async function fetchInvestigationGraph(investigationId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/graph`, {
    method: 'GET',
    params,
  });
}

export async function fetchInvestigationChronology(investigationId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/chronology`, {
    method: 'GET',
    params,
  });
}

export async function fetchInvestigationInfrastructure(investigationId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/infrastructure`, {
    method: 'GET',
    params,
  });
}

export async function fetchInvestigationActors(investigationId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/actors`, {
    method: 'GET',
    params,
  });
}

export async function fetchInvestigationActorProfile(investigationId, actorId, params = {}) {
  return apiRequest(`/investigations/${investigationId}/actors/${actorId}`, {
    method: 'GET',
    params,
  });
}

export async function generateDossierReportApi(investigationId, body = {}) {
  return apiRequest(`/investigations/${investigationId}/reports`, {
    method: 'POST',
    body,
  });
}

export async function fetchInvestigationReports(investigationId) {
  return apiRequest(`/investigations/${investigationId}/reports`);
}

export async function downloadReportFileApi(investigationId, reportId, filename = 'dossier') {
  const url = `${API_BASE_URL}/investigations/${investigationId}/reports/${reportId}/download`;
  const headers = {};
  const storedToken = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(TOKEN_KEY) : null;
  if (storedToken) {
    headers.Authorization = `Bearer ${storedToken}`;
  }
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Download failed with status ${res.status}`);
  }
  const blob = await res.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(downloadUrl);
}

