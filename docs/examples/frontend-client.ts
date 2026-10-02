/** Framework-neutral JSON client for the documented journey; tokens stay in memory. */
export type Success<T> = {
  success: true;
  request_id: string;
  error: null;
  code: number;
  data: T;
};
export type Page<T> = {
  success: true;
  request_id: string;
  error: null;
  code: number;
  result: { items: T[]; page: number; size: number; total: number; total_pages: number };
};
export type Tokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};
// Minimal projections used by this example. Consult OpenAPI for the full DTOs.
export type BusinessRequest = { ref_id: string; status: string; data: Record<string, unknown> };
export type WorkItem = { ref_id: string; request_ref_id: string; status: string };
export type TaskAction = {
  key: string;
  kind: "complete" | "reject" | "return";
  outcome_key: string;
  title: string;
  confirmation: string | null;
  required_scopes: string[];
  require_comment: boolean;
  validation: "complete" | "partial";
};
export type TaskView = {
  work_item_ref_id: string;
  data: Record<string, unknown>;
  actions: TaskAction[];
};

export class ApiError extends Error {
  constructor(public status: number, public body: unknown) {
    super(`API request failed (HTTP ${status})`);
  }
}

export class FrontendClient {
  private tokens: Tokens | null = null;
  private refreshPending: Promise<void> | null = null;

  constructor(private baseUrl = "/api/v1") {}

  private async json<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { "Accept-Language": "en" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (this.tokens) headers.Authorization = `Bearer ${this.tokens.access_token}`;
    const response = await fetch(`${this.baseUrl}${path}`, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    let payload: unknown;
    try { payload = await response.json(); }
    catch { throw new ApiError(response.status, { error: "Non-JSON server response" }); }
    if (!response.ok || (typeof payload === "object" && payload !== null &&
        "success" in payload && payload.success === false)) {
      throw new ApiError(response.status, payload);
    }
    // A generic type is not runtime validation. Production callers may use a generated validator.
    return payload as T;
  }

  async login(username: string, password: string): Promise<void> {
    // Serialize session transitions with this instance's in-flight refresh.
    await this.refreshPending?.catch(() => {});
    this.tokens = null;
    const response = await this.json<Success<Tokens>>("POST", "/auth/login", {
      username, password, device_name: "Documentation browser",
    });
    this.tokens = response.data;
  }

  refresh(): Promise<void> {
    if (this.refreshPending) return this.refreshPending;
    if (!this.tokens) return Promise.reject(new Error("Sign in first"));
    const refresh_token = this.tokens.refresh_token;
    this.refreshPending = this.json<Success<Tokens>>("POST", "/auth/refresh", { refresh_token })
      .then(response => { this.tokens = response.data; })
      .catch(error => { this.tokens = null; throw error; })
      .finally(() => { this.refreshPending = null; });
    return this.refreshPending;
  }

  async logout(): Promise<void> {
    await this.refreshPending?.catch(() => {});
    if (!this.tokens) return;
    try { await this.json("POST", "/auth/logout", { refresh_token: this.tokens.refresh_token }); }
    finally { this.tokens = null; }
  }

  createDraft(request_type_ref_id: string, data: Record<string, unknown>) {
    return this.json<Success<BusinessRequest>>("POST", "/business-requests", {
      request_type_ref_id, priority: 5, data,
    });
  }

  saveDraft(ref: string, data: Record<string, unknown>) {
    return this.json<Success<BusinessRequest>>("PUT", `/business-requests/${encodeURIComponent(ref)}`, {
      priority: 5, data,
    });
  }

  submit(ref: string, submit_key: string) {
    return this.json<Success<BusinessRequest>>("POST", `/business-requests/${encodeURIComponent(ref)}/submit`, { submit_key });
  }

  available(page = 1) {
    return this.json<Page<WorkItem>>("POST", "/work-items/search", { cartable: "available", page, size: 20 });
  }

  claim(ref: string, command_key: string) {
    return this.json<Success<WorkItem>>("POST", `/work-items/${encodeURIComponent(ref)}/claim`, { command_key });
  }

  view(ref: string) {
    return this.json<Success<TaskView>>("GET", `/work-items/${encodeURIComponent(ref)}/view`);
  }

  finish(view: TaskView, action: TaskAction, data: Record<string, unknown>, command_key: string, comment: string | null = null) {
    if (!view.actions.some(candidate => candidate.key === action.key && candidate.kind === action.kind && candidate.outcome_key === action.outcome_key)) {
      throw new Error("Choose an action from the current task view");
    }
    if (action.require_comment && !comment?.trim()) throw new Error("A comment is required");
    return this.json<Success<WorkItem>>("POST", `/work-items/${encodeURIComponent(view.work_item_ref_id)}/${action.kind}`, {
      command_key, outcome_key: action.outcome_key, data, comment, feedback: [],
    });
  }

  request(ref: string) {
    return this.json<Success<BusinessRequest>>("GET", `/business-requests/${encodeURIComponent(ref)}`);
  }
}

/** Call only after the user confirms submission; retain submitKey to reconcile uncertain results. */
export async function submitExample(client: FrontendClient, requestTypeRef: string, submitKey: string) {
  let current = (await client.createDraft(requestTypeRef, { amount: "125.00" })).data;
  current = (await client.saveDraft(current.ref_id, { amount: "125.00" })).data;
  return (await client.submit(current.ref_id, submitKey)).data;
}

// Reviewer flow (separate client/session): available → choose task → claim → view → user decision → finish.
// Generate command keys outside retry callbacks, e.g. crypto.randomUUID(). Never auto-approve the first action.
// Do not repeat submitExample after a network failure: reconcile the already created draft/action first.
