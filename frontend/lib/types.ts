export interface TherapyOption {
  dose: string;
  duration: string;
  total_doses: number | null;
}

export interface Chemo {
  name: string;
  route: string;
  frequency: string;
  options?: TherapyOption[]; // <--- The radio button options array!
  
  // Base fallbacks for the calendar generator
  dose: string;
  duration: string;
  total_doses?: number | null;
}

export interface Regimen {
  name: string;
  disease_state?: string | null;
  on_study: boolean;
  notes?: string | null;
  therapies: Chemo[];
  created_by?: string | null;
  updated_by?: string | null;
}

export interface CalendarCell {
  date: string;
  cycle_day: number | null;
  labels: string[];
}

export interface CalendarPreviewResponse {
  header: string;
  label: string;
  regimen_title: string;
  first_sun: string;
  last_sat: string;
  grid: CalendarCell[][];
}

export interface RegimenSummary {
  name: string;
  disease_state: string | null;
  on_study: boolean;
  created_by?: string | null;
  updated_by?: string | null;
}

export interface User {
  username: string;
  display_name: string | null;
  created_at: string | null;
}

export interface AuditEntry {
  id: number;
  regimen_id: number | null;
  regimen_name: string;
  action: "create" | "update" | "delete" | string;
  username: string;
  timestamp: string;
  diff: {
    before?: Record<string, any> | null;
    after?: Record<string, any> | null;
    fields_changed?: string[];
  };
}

export interface CalendarPreviewRequest {
  regimen_name: string;
  title_override?: string | null;
  start_date: string; // YYYY-MM-DD
  cycle_len: number;
  phase: "Cycle" | "Induction";
  cycle_num?: number | null;
  note?: string | null;
  therapies_override?: Chemo[]; // <--- Allows sending radio button choices to backend
}