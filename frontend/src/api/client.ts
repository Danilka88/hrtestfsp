import axios, { AxiosError } from "axios";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";
const TOKEN_KEY = "it-talent-access";
const REFRESH_KEY = "it-talent-refresh";

export const tokenStore = {
  access: () => localStorage.getItem(TOKEN_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  save(access: string, refresh?: string) {
    localStorage.setItem(TOKEN_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = tokenStore.access();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) tokenStore.clear();
    return Promise.reject(error);
  },
);

/** Человекочитаемое сообщение об ошибке API. */
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0] as { msg?: string };
      if (first?.msg) return first.msg;
    }
    if (!error.response) return "Сервис недоступен — проверьте, запущен ли backend";
  }
  return "Не удалось выполнить запрос";
}

// --- Типы -------------------------------------------------------------------

export type Role = "candidate" | "employer";

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface ReadyResponse {
  status: string;
  database: string;
  providers: Record<string, boolean>;
}

export interface UserPublic {
  id: string;
  email: string;
  role: string;
  email_verified: boolean;
  is_active: boolean;
  fsp_id: string | null;
  created_at: string;
  consent_pdn_at: string | null;
  consent_publish_at: string | null;
}

export interface RegisterResponse {
  user_id: string;
  email: string;
  role: string;
  email_verified: boolean;
  message: string;
  verification_token: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface CandidateProfile {
  id: string;
  full_name: string | null;
  specialization: string | null;
  grade: string | null;
  experience_years: number | null;
  stack: string[];
  roles: string[];
  soft_skills: string[];
  summary: string | null;
  resume_source: string;
  privacy: Record<string, boolean>;
}

export interface Specialization {
  id: number;
  code: string;
  title: string;
}

export interface Grade {
  code: string;
  title: string;
  rank_order: number;
}

export interface SurveyResult {
  id: string;
  specialization_code: string;
  grade_options: string[];
}

export interface TestItem {
  id: string;
  skill_tag: string;
  question: string | null;
  options: string[];
}

export interface StartSessionResult {
  session_id: string;
  target_grade: string;
  item: TestItem;
  note: string;
}

export interface SessionResult {
  session_id: string;
  status: string;
  items_answered: number;
  theta: number;
  standard_error: number;
  converged: boolean;
  result_grade: string;
  current_grade: string | null;
  grade_change_applied: boolean;
  grade_change_reason: string;
  warnings: string[];
}

export interface AnswerResult {
  correct: boolean;
  finished: boolean;
  next_item: TestItem | null;
  result: SessionResult | null;
}

export interface CategoryStatus {
  specialization: string | null;
  grade: string | null;
  grade_change_allowed: boolean;
  grade_change_available_in_days: number | null;
  grade_change_cooldown_days: number;
  grade_options: string[];
  grade_history: { from_grade: string | null; to_grade: string; at: string }[];
  sessions: {
    id: string;
    status: string;
    target_grade: string;
    result_grade: string | null;
    items_answered: number;
    theta: number;
  }[];
}

export interface Reason {
  code: string;
  text: string;
  value: number;
  contribution: number;
}

export interface CandidateCard {
  reference: string;
  full_name: string | null;
  specialization: string | null;
  grade: string | null;
  category_id: number | null;
  stack: string[];
  experience_years: number | null;
  fsp_achievements: number | null;
  contacts_visible: boolean;
  rank: number;
  score: number;
  reasons: Reason[];
  missing: string[];
}

export interface Selection {
  id: string;
  title: string;
  parent_selection_id: string | null;
  rubric_version: string;
  params: Record<string, unknown>;
  recommended_categories: number[];
  candidates: CandidateCard[];
  created_at: string;
}

export interface EmployerInvitation {
  id: string;
  candidate_reference: string;
  candidate_name: string | null;
  candidate_specialization: string | null;
  candidate_grade: string | null;
  message: string | null;
  salary_from: number;
  salary_to: number;
  status: string;
  created_at: string;
  contacts_revealed: boolean;
  candidate_contacts: {
    email?: string | null;
    phone?: string | null;
    telegram?: string | null;
  } | null;
}

export interface CandidateInvitation {
  id: string;
  company_name: string | null;
  company_description: string | null;
  message: string | null;
  salary_from: number;
  salary_to: number;
  contact_method: string | null;
  status: string;
  created_at: string;
}

export interface FspStatus {
  fsp_id: string | null;
  linked: boolean;
  achievements: { contest: string; category: string; year: number; place: number | null }[];
  note: string;
}

// --- Служебные --------------------------------------------------------------

export async function fetchHealth(): Promise<HealthResponse> {
  return (await api.get<HealthResponse>("/health")).data;
}

export async function fetchReady(): Promise<ReadyResponse> {
  return (await api.get<ReadyResponse>("/health/ready")).data;
}

// --- Аутентификация ---------------------------------------------------------

export async function register(input: {
  email: string;
  password: string;
  role: Role;
  consent_pdn: boolean;
  consent_publish?: boolean;
}): Promise<RegisterResponse> {
  return (await api.post<RegisterResponse>("/auth/register", input)).data;
}

export async function verifyEmail(token: string): Promise<UserPublic> {
  return (await api.post<UserPublic>("/auth/verify-email", { token })).data;
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const data = (await api.post<TokenPair>("/auth/login", { email, password })).data;
  tokenStore.save(data.access_token, data.refresh_token);
  return data;
}

export async function logout(): Promise<void> {
  const refresh = tokenStore.refresh();
  if (refresh) {
    try {
      await api.post("/auth/logout", { refresh_token: refresh });
    } catch {
      /* выход должен работать и при недоступном сервисе */
    }
  }
  tokenStore.clear();
}

export async function me(): Promise<UserPublic> {
  return (await api.get<UserPublic>("/auth/me")).data;
}

// --- Кандидат ---------------------------------------------------------------

export async function getCandidateProfile(): Promise<CandidateProfile> {
  return (await api.get<CandidateProfile>("/candidates/me/profile")).data;
}

export async function putCandidateProfile(
  payload: Record<string, unknown>,
): Promise<CandidateProfile> {
  return (await api.put<CandidateProfile>("/candidates/me/profile", payload)).data;
}

export async function listSpecializations(): Promise<Specialization[]> {
  return (await api.get<Specialization[]>("/testing/specializations")).data;
}

export async function listGrades(): Promise<Grade[]> {
  return (await api.get<Grade[]>("/testing/grades")).data;
}

export async function submitSurvey(
  specialization_code: string,
  answers: Record<string, string> = {},
): Promise<SurveyResult> {
  return (
    await api.post<SurveyResult>("/testing/survey", {
      industry: "it",
      specialization_code,
      answers,
    })
  ).data;
}

export async function startSession(
  specialization_code: string,
  target_grade: string,
): Promise<StartSessionResult> {
  return (
    await api.post<StartSessionResult>("/testing/sessions", {
      specialization_code,
      target_grade,
    })
  ).data;
}

export async function answerItem(
  sessionId: string,
  itemId: string,
  answerIndex: number,
  responseTimeMs: number,
): Promise<AnswerResult> {
  return (
    await api.post<AnswerResult>(`/testing/sessions/${sessionId}/answers`, {
      item_id: itemId,
      answer_index: answerIndex,
      response_time_ms: responseTimeMs,
    })
  ).data;
}

export async function myCategory(): Promise<CategoryStatus> {
  return (await api.get<CategoryStatus>("/testing/me/category")).data;
}

export async function myInvitations(): Promise<CandidateInvitation[]> {
  return (await api.get<CandidateInvitation[]>("/candidates/me/invitations")).data;
}

export async function viewInvitation(id: string): Promise<CandidateInvitation> {
  return (await api.post<CandidateInvitation>(`/candidates/me/invitations/${id}/view`)).data;
}

export async function decideInvitation(
  id: string,
  status: "accepted" | "declined",
): Promise<CandidateInvitation> {
  return (
    await api.post<CandidateInvitation>(`/candidates/me/invitations/${id}/decision`, { status })
  ).data;
}

export async function getFsp(): Promise<FspStatus> {
  return (await api.get<FspStatus>("/candidates/me/fsp")).data;
}

export async function linkFsp(fsp_id: string | null): Promise<FspStatus> {
  return (await api.put<FspStatus>("/candidates/me/fsp", { fsp_id })).data;
}

// --- Работодатель -----------------------------------------------------------

export async function getEmployerProfile(): Promise<Record<string, unknown>> {
  return (await api.get("/employers/me/profile")).data;
}

export async function putEmployerProfile(payload: Record<string, unknown>): Promise<unknown> {
  return (await api.put("/employers/me/profile", payload)).data;
}

export async function createNeed(payload: {
  title: string;
  description?: string;
  specialization_code?: string;
  grade?: string;
  stack?: string[];
  salary_from?: number;
  salary_to?: number;
}): Promise<Selection> {
  return (await api.post<Selection>("/employers/me/needs", payload)).data;
}

export interface SelectionSummary {
  id: string;
  title: string;
  candidates_count: number;
  parent_selection_id: string | null;
}

export async function listSelections(): Promise<SelectionSummary[]> {
  return (await api.get<SelectionSummary[]>("/employers/me/selections")).data;
}

export async function getSelection(id: string): Promise<Selection> {
  return (await api.get<Selection>(`/employers/me/selections/${id}`)).data;
}

/**
 * Уточнение подборки: создаётся НОВАЯ подборка, прежняя сохраняется
 * (в ответе заполнено parent_selection_id).
 */
export async function refineSelection(
  id: string,
  params: { stack?: string[]; grade?: string } = {},
): Promise<Selection> {
  return (
    await api.post<Selection>(`/employers/me/selections/${id}/refine`, null, {
      params,
      // FastAPI ожидает повторяющийся параметр (?stack=a&stack=b), поэтому
      // отключаем индексацию массивов в сериализаторе axios.
      paramsSerializer: { indexes: null },
    })
  ).data;
}

export async function employerInvitations(): Promise<EmployerInvitation[]> {
  return (await api.get<EmployerInvitation[]>("/employers/me/invitations")).data;
}

export async function sendInvitation(payload: {
  candidate_reference: string;
  message?: string;
  salary_from: number;
  salary_to: number;
  contact_method?: string;
}): Promise<EmployerInvitation> {
  return (await api.post<EmployerInvitation>("/employers/me/invitations", payload)).data;
}

export async function searchCandidates(
  params: Record<string, string | number | boolean | string[]>,
): Promise<{ total: number; candidates: CandidateCard[] }> {
  return (
    await api.get("/employers/me/search", {
      params,
      // FastAPI ожидает повторяющийся параметр (?stack=a&stack=b).
      paramsSerializer: { indexes: null },
    })
  ).data;
}

// --- Вакансии (дополнительный функционал) -----------------------------------

export interface Vacancy {
  id: string;
  title: string;
  description: string | null;
  specialization_code: string | null;
  grade: string | null;
  stack: string[];
  salary_from: number;
  salary_to: number;
  status: string;
  company_name: string | null;
  created_at: string;
}

export interface ApplicationCandidate {
  id: string;
  vacancy_id: string;
  vacancy_title: string | null;
  company_name: string | null;
  message: string | null;
  status: string;
  created_at: string;
  viewed_at: string | null;
  decided_at: string | null;
}

export interface ApplicationEmployer {
  id: string;
  vacancy_id: string;
  candidate_reference: string;
  candidate_name: string | null;
  candidate_specialization: string | null;
  candidate_grade: string | null;
  candidate_stack: string[];
  message: string | null;
  status: string;
  created_at: string;
  candidate_contacts: { email?: string | null; phone?: string | null; telegram?: string | null } | null;
  contacts_revealed: boolean;
}

export async function listOpenVacancies(specializationCode?: string): Promise<Vacancy[]> {
  return (
    await api.get<Vacancy[]>("/candidates/me/vacancies", {
      params: specializationCode ? { specialization_code: specializationCode } : {},
    })
  ).data;
}

export async function applyToVacancy(vacancyId: string, message: string): Promise<ApplicationCandidate> {
  return (
    await api.post<ApplicationCandidate>(`/candidates/me/vacancies/${vacancyId}/applications`, { message })
  ).data;
}

export async function myApplications(): Promise<ApplicationCandidate[]> {
  return (await api.get<ApplicationCandidate[]>("/candidates/me/applications")).data;
}

export async function listMyVacancies(): Promise<Vacancy[]> {
  return (await api.get<Vacancy[]>("/employers/me/vacancies")).data;
}

export async function publishVacancy(payload: {
  title: string;
  description?: string;
  specialization_code?: string;
  grade?: string;
  stack?: string[];
  salary_from: number;
  salary_to: number;
}): Promise<Vacancy> {
  return (await api.post<Vacancy>("/employers/me/vacancies", payload)).data;
}

export async function closeVacancy(vacancyId: string): Promise<Vacancy> {
  return (await api.post<Vacancy>(`/employers/me/vacancies/${vacancyId}/close`)).data;
}

export async function vacancyApplications(vacancyId: string): Promise<ApplicationEmployer[]> {
  return (await api.get<ApplicationEmployer[]>(`/employers/me/vacancies/${vacancyId}/applications`)).data;
}

export async function decideApplication(
  applicationId: string,
  status: "accepted" | "declined",
): Promise<ApplicationEmployer> {
  return (
    await api.post<ApplicationEmployer>(`/employers/me/vacancies/applications/${applicationId}/decision`, {
      status,
    })
  ).data;
}

// --- Регулярные короткие задания --------------------------------------------

export interface RegularTask {
  id: string;
  title: string;
  description: string | null;
  specialization_code: string | null;
  grade: string | null;
  status: string;
  company_name: string | null;
  created_at: string;
}

export interface TaskSubmission {
  id: string;
  task_id: string;
  candidate_reference: string | null;
  candidate_name: string | null;
  candidate_specialization: string | null;
  candidate_grade: string | null;
  solution: string;
  status: string;
  created_at: string;
}

export async function listMyTasks(): Promise<RegularTask[]> {
  return (await api.get<RegularTask[]>("/employers/me/tasks")).data;
}

export async function createTask(payload: {
  title: string;
  description?: string;
  specialization_code?: string;
  grade?: string;
}): Promise<RegularTask> {
  return (await api.post<RegularTask>("/employers/me/tasks", payload)).data;
}

export async function taskSubmissions(taskId: string): Promise<TaskSubmission[]> {
  return (await api.get<TaskSubmission[]>(`/employers/me/tasks/${taskId}/submissions`)).data;
}

export async function offeredTasks(): Promise<RegularTask[]> {
  return (await api.get<RegularTask[]>("/candidates/me/tasks")).data;
}

export async function submitTask(taskId: string, solution: string): Promise<TaskSubmission> {
  return (await api.post<TaskSubmission>(`/candidates/me/tasks/${taskId}/submissions`, { solution })).data;
}

// --- ИИ ---------------------------------------------------------------------

export interface AIStatus {
  provider: string;
  available: boolean;
  degraded: boolean;
  model: string | null;
  base_url?: string | null;
  think?: boolean | null;
  detail?: string | null;
  hint: string;
}

export interface AIResult<T = Record<string, unknown>> {
  data: T;
  provider: string;
  degraded: boolean;
  latency_ms: number;
  note: string | null;
  warnings: string[];
}

export async function aiStatus(): Promise<AIStatus> {
  return (await api.get<AIStatus>("/ai/status")).data;
}

export async function aiNeedDraft(brief: string): Promise<AIResult> {
  return (await api.post<AIResult>("/ai/need/draft", { brief })).data;
}

export async function aiTaskDraft(payload: {
  need_title: string;
  stack?: string[];
  grade?: string;
}): Promise<AIResult> {
  return (await api.post<AIResult>("/ai/task/draft", payload)).data;
}

export async function aiInvitationDraft(payload: {
  company: string;
  candidate_grade?: string | null;
  stack?: string[];
  salary_from: number;
  salary_to: number;
  role_title?: string | null;
}): Promise<AIResult> {
  return (await api.post<AIResult>("/ai/invitation/draft", payload)).data;
}

export async function aiProfileAnalyze(text: string): Promise<AIResult> {
  return (await api.post<AIResult>("/ai/profile/analyze", { text })).data;
}

export async function aiCoverLetter(payload: {
  vacancy_title: string;
  company: string;
  required_stack?: string[];
  candidate_stack?: string[];
  candidate_grade?: string | null;
}): Promise<AIResult> {
  return (await api.post<AIResult>("/ai/cover-letter", payload)).data;
}

export async function aiMatchExplain(payload: {
  selection_id: string;
  candidate_reference: string;
}): Promise<AIResult> {
  return (await api.post<AIResult>("/ai/match/explain", payload)).data;
}
