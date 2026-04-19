export type Chemo = {
  name: string;
  route: string;
  dose: string;
  frequency: string;
  duration: string;
  total_doses?: number | null;
};

export type Regimen = {
  name: string;
  disease_state?: string | null;
  on_study: boolean;
  notes?: string | null;
  therapies: Chemo[];
};

export type CalendarCell = {
  date: string; // YYYY-MM-DD
  cycle_day: number | null;
  labels: string[];
};

export type CalendarPreviewResponse = {
  header: string;
  label: string;
  regimen_title: string;
  first_sun: string;
  last_sat: string;
  grid: CalendarCell[][];
};

export type CalendarPreviewRequest = {
  regimen_name: string;
  title_override?: string | null;
  start_date: string; // YYYY-MM-DD
  cycle_len: number;
  phase: "Cycle" | "Induction";
  cycle_num?: number | null;
  note?: string | null;
};