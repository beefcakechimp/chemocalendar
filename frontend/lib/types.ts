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