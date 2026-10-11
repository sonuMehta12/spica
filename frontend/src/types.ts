/** Three, and the deck's rule says three. Screen time was a fourth card on
 *  hardcoded data; it was removed on 2026-09-07 — not building it. */
export type Mode = 'paisa' | 'diet' | 'work';
export type Range = 'aaj' | '7din' | '30din' | 'sab';

export interface Tx {
  id: string;
  /** Day of the month. */
  day: number;
  name: string;
  cat: string;
  amt: number;
  /** Written optimistically; the server has not confirmed it yet. */
  pending?: boolean;
  /** The server refused or never answered. The row STAYS — visibly unsaved. */
  failed?: boolean;
  /** The commitment this payment counts toward. Set means committed — not
   *  discretionary spend. spec/done/commitments.md */
  commitmentId?: string | null;
  /** The link was a guess from the category: an amber dot until moved or confirmed. */
  commitmentInferred?: boolean;
  /** Money coming IN — salary, a repayment returning, something borrowed.
   *  Renders +green rather than −red, and never counts as an expense. */
  credit?: boolean;
  /** ISO local day. Set on rows fetched by id from outside the deck's window. */
  date?: string;
  /** Soft-deleted on the server. Only the by-id read returns such rows. */
  deleted?: boolean;
  /** The row's own confidence; below 1 means a value on it was the agent's guess. */
  confidence?: number;
  /** The ledger's kind — expense, income, lent, borrowed, repayment. Udhaar's
   *  three never ask a category: a loan is a loan, not a guess. */
  kind?: string;
}

export interface Meal {
  id: string;
  day: number;
  name: string;
  /** Breakfast / Lunch / Grazing… — free text, as logged. */
  type?: string;
  /** Protein, grams. */
  p: number;
  /** Energy, kcal. */
  k: number;
  /** Carbs, grams. Undefined = not known — never 0 standing in for unknown. */
  c?: number;
  /** Fat, grams. Same rule. */
  f?: number;
  pending?: boolean;
  failed?: boolean;
  date?: string;
  deleted?: boolean;
  confidence?: number;
}

/** Which surface a task belongs to. Decides where it shows up. */
export type TaskKind = 'work' | 'paisa' | 'diet';

export interface Todo {
  id: string;
  name: string;
  done: boolean;
  kind: TaskKind;
  /**
   * The ISO local day it was ticked. Lets a task stay on the card with a
   * completed status for the rest of the day, then drop off — without it,
   * either finished work vanishes the instant you tick it, or last week's
   * ticks clog the list forever.
   *
   * A day-of-month number here read 12 August's tick as today's; see
   * `src/lib/day.ts`.
   */
  doneOn?: string;
  /** Project id. Every task has one; the default takes the rest. */
  project?: string;
  /** The model chose the project, not the person — the amber dot. */
  projectGuessed?: boolean;
  /** The ISO local day it is due. Undefined means backlog: real, but undated. */
  due?: string;
  /** 1 is most urgent. Undefined sorts last. */
  priority?: number;
  /** Where it came from — `spec/x.md:44`, `Linear · ENG-142`, a meeting's title. */
  src?: string;
  /** The issue itself, for a task from a tracker. */
  link?: string;
  /** The tracker's stage, in the team's own word. */
  stage?: string;
  /** From a tracker: ticking it here means moving it there next. */
  tracked?: boolean;
  /** The tracker's name — `Linear`. */
  origin?: string;
  /** Done here, not yet moved in the tracker — the reminder is showing. */
  awaitingMove?: boolean;
}

/** One habit on one day, and how much of it there was. */
export interface HabitMark {
  habit: string;
  /** Summed over the day's logs — one `×2` log and two `×1` logs both read 2. */
  count: number;
}

/** One mark on the Diet card's week strip. Every slot is a real calendar day,
 *  including the ones belonging to the month before. */
export interface ChainDay {
  day: number;
  /** ISO local day — the identity. `day` is only its number. */
  date: string;
  letter: string;
  done: boolean;
  /** Every habit logged that day — one stacked icon each, whatever its count. */
  habits: HabitMark[];
  isToday: boolean;
  /** Hasn't happened yet — drawn faint, because it is not a day you skipped. */
  future: boolean;
}

/**
 * A session you actually did — a ledger row, the instance. The *plan* it came
 * from is a library item (`ItemKind: 'workout'` in the vault), the same split
 * Recipe and Meal log have.
 */
export interface Workout {
  id: string;
  /** Day of the month, like every other ledger row. */
  day: number;
  /** Free text on purpose — the agent should not refuse to log "kabaddi". */
  kind: string;
  minutes?: number;
  source: 'manual' | 'voice';
}

/** One project's standing, as the Work card's bar chart draws it. */
export interface ProjectStat {
  id: string;
  name: string;
  color: string;
  done: number;
  total: number;
  /** Open tasks whose date has already passed. */
  late: number;
}

/** One thing you are building. Its colour keys a bar on the Work card. */
export interface Project {
  id: string;
  name: string;
  color: string;
  /** What it is, in their words — what placement reads. */
  description?: string;
  /** An emoji, or `icon:<name>` from the app's set. Absent draws the first letter. */
  icon?: string;
  /** What it is called elsewhere — `linear:Kestrel`, a nickname. */
  aliases?: string[];
  /** Where anything unplaced lands. Exactly one. */
  isDefault?: boolean;
}

/**
 * What a card's Change hangs on the composer — an annotation, like a quote:
 * `label` is the pill ("Auto · category"), `prefix` the words the agent is
 * sent before whatever is typed. Nothing is put in the text box itself.
 */
export interface ComposerContext {
  label: string;
  prefix: string;
}

/** A line the user said (or a `@tool` they invoked). */
export interface UserMsg {
  kind: 'user';
  id: string;
  /** What was typed — the bubble. With a context, the agent got the prefix before it. */
  text: string;
  /** The row it was said about, drawn as a faint line above the bubble. */
  context?: ComposerContext;
  /** It never reached the server. The bubble itself says so, with Retry —
   *  it was yours that did not go, so no agent bubble speaks for it. */
  failed?: boolean;
}

/** The agent's reply: a formatted line and its explanation, nothing else. */
export interface AgentMsg {
  kind: 'agent';
  id: string;
  title: string;
  hl: string;
  hlColor: string;
  body: string;
}

/**
 * A ledger table. Stores row *ids* rather than snapshots so the card keeps
 * tracking live data — deleting a row from one table updates every table.
 */
export interface TableMsg {
  kind: 'table';
  id: string;
  heading: string;
  source: 'paisa' | 'diet';
  ids: string[];
}

/**
 * Cash flow, from the + menu. Nothing but an id: the card works out the month
 * from the live rows every time it is drawn, like the to-do list does.
 */
export interface FlowMsg {
  kind: 'flow';
  id: string;
}

/**
 * What is owed this month, from the agent's `commitments` read. No rows: the
 * card draws the current month's commitments from live state, so an edit or a
 * delete anywhere shows here, like the to-do list.
 */
export interface CommitmentsMsg {
  kind: 'commitments';
  id: string;
}

export interface TodoMsg {
  kind: 'todo';
  id: string;
  /** `work` comes from the Kaam card; the tray's To-do asks for everything. */
  scope: 'all' | 'work';
  /** A project's name: the list narrows to it, matched by name, any case. */
  project?: string | null;
  /** The agent answered with it (`todos`): its reply above is the line, so the card draws none. */
  agent?: boolean;
}

/**
 * The pantry or your dishes, from the + menu. Which
 * list, and nothing else: rows and the line above them are read live at
 * render time, so a meal that uses up the paneer changes the card it named.
 */
export interface PantryMsg {
  kind: 'pantry';
  id: string;
  list: 'pantry' | 'dishes';
}

/** One editable field on a confirm card. `guessed` draws the amber dot. */
export interface ConfirmField {
  key: string;
  label: string;
  value: string;
  guessed: boolean;
}

/**
 * A write the agent made, with the parts it worked out marked so one tap fixes
 * them. `lede` leads with what is LEFT — never with what was consumed.
 */
/** Which route a confirm card's tray calls. */
export type ConfirmSource =
  | 'paisa'
  | 'diet'
  | 'body'
  | 'pantry'
  | 'people'
  | 'places'
  | 'memory'
  | 'profile'
  | 'work'
  | 'commitment';

export interface ConfirmMsg {
  kind: 'confirm';
  id: string;
  source: ConfirmSource;
  rowId: string | null;
  /** `deleted` strikes the lede and drops the tray — the row is history. */
  state: 'written' | 'proposed' | 'deleted';
  lede: string;
  fields: ConfirmField[];
  /** Items the agent could not match at all. Shown, never guessed at. */
  unresolved: string[];
  /** Matched, but with no weight — "2 roti" is not two grams of atta. Their
   *  macros are missing from the total, so the card says so. */
  needsQuantity: string[];
}

/**
 * One thing to eat or do. The display fields are reference values on the dish
 * or exercise — carrying them is allowed; a claim about the user is not.
 */
export interface SuggestItem {
  type: 'dish' | 'exercise';
  ref: string;
  name: string;
  why: string;
  saved: boolean;
  mealType: string | null;
  minutes: number | null;
  proteinG: number | null;
  kcal: number | null;
  imageUrl: string | null;
  missing: string[];
  exerciseKind: string | null;
  muscleGroup: string | null;
  tried: number | null;
}

export interface SuggestMsg {
  kind: 'suggest';
  id: string;
  items: SuggestItem[];
}

/** One question, and only when the answer changes a number. */
export interface AskMsg {
  kind: 'ask';
  id: string;
  question: string;
  options: string[];
  /** The write this question is holding up, if any. */
  pendingRowId: string | null;
}

export type ChatMsg =
  | UserMsg
  | AgentMsg
  | TableMsg
  | FlowMsg
  | TodoMsg
  | CommitmentsMsg
  | PantryMsg
  | ConfirmMsg
  | SuggestMsg
  | AskMsg;

export interface Suggestion {
  id: string;
  name: string;
  tag: string;
}

/** One arc of the concentric hero, with the numbers that float at its tip. */
export interface RingSpec {
  key: string;
  /** Tiny uppercase caption, e.g. "MAHINA", "PROTEIN". */
  caption: string;
  valueStr: string;
  totalStr: string;
  /** 0–1 of the way round. Values over 1 are clamped when drawn. */
  pct: number;
  color: string;
  /**
   * Optional flat leading segment drawn before the live one — money already
   * committed for the month. The arc tip still sits at `pct`.
   */
  basePct?: number;
}

/**
 * One page of the swipeable primary component: a stack of concentric arcs,
 * outermost first, each labelled at its own tip.
 */
export interface HeroView {
  mode: Mode;
  label: string;
  live: boolean;
  rings: RingSpec[];
  /** Diet only: the "+ aur" drawer for macros that have no ring. */
  hasMacros: boolean;
  /** Work only: one entry per project, for the bar chart. */
  projects?: ProjectStat[];
  /** Diet only: the week's training marks, Monday first. */
  chain?: ChainDay[];
  chainCount?: number;
  /** Diet only: '6/7 din logged' — the denominator behind an average. */
  coverage?: string;
  /** Paisa only: last month's repeating costs not yet paid this month, held out of the pool. */
  locked?: number;
  /**
   * The band under the arcs: one labelled number per column, two rows total.
   *
   * It used to be three projected savings rates and a hardcoded goal. Those
   * answered a question nobody asked while `committed` — the number that
   * explains a ₹0 limit — was hidden inside the ⋮ menu.
   * spec/done/commitments.md § the card.
   */
  strip?: {
    key: string;
    label: string;
    value: string;
    tone?: 'ink' | 'red';
  }[];

  /** Month-end outcome at three daily rates. */
  /** Work only: the next few dated tasks, already sorted. */
  tasks?: Todo[];
  /** Work only: everything still open, for the "see all" row. */
  openCount?: number;
  /** Dormant pages show this instead of arcs. */
  note?: string;
}
