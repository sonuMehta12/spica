import { BowlFood, Clock, Heartbeat, Repeat, Wallet, type Icon } from '@phosphor-icons/react';
import { BRAND } from '../brand';
import type { OnboardingQuestion } from '../data/api';
import { color } from '../theme';

/**
 * The first run's fixed words. spec/done/onboarding-goals.md § 2 and § 3.
 *
 * The questions are copy, not the agent's to phrase: they are asked exactly
 * as written here, and the onboarding agent's prompt knows them by the same
 * names (`backend/app/agent/skills/onboarding.md`).
 */

/** Screen 2's picks: what you get, not a feature name. Five picks, three domains. */
export type PickId = 'money' | 'eating' | 'health' | 'habits' | 'time';

export interface Pick {
  id: PickId;
  title: string;
  line: string;
  icon: Icon;
  /** The domain's tint and ink: money Paisa's, food, body and habits Diet's, time Work's. */
  tint: string;
  ink: string;
}

export const PICKS: readonly Pick[] = [
  { id: 'money', title: 'Your money', line: 'Know where it goes. Keep more of it.', icon: Wallet, tint: color.paisaTint, ink: color.paisaInk },
  { id: 'eating', title: 'Eating healthy', line: 'Better meals, no counting.', icon: BowlFood, tint: color.dietTint, ink: color.dietInk },
  { id: 'health', title: 'Your health', line: 'Weight, sleep, workouts — moving right.', icon: Heartbeat, tint: color.dietTint, ink: color.dietInk },
  { id: 'habits', title: 'Your habits', line: 'Build the good ones. Cut the rest.', icon: Repeat, tint: color.dietTint, ink: color.dietInk },
  { id: 'time', title: 'Your time', line: 'Work on track, and your evenings back.', icon: Clock, tint: color.workTint, ink: color.workInk },
];

export const HELLO = `Hi, I’m ${BRAND}.`;
export const TAKE_CONTROL = 'What do you want to take control of? I’ll help you get there.';

export interface Question {
  id: OnboardingQuestion;
  /** What Spica says, line by line. */
  says: readonly string[];
  /** Words a tap adds to the answer. */
  chips: readonly string[];
  /** The pick that asks it; null is always asked. */
  when: PickId | null;
}

/** In the order they are asked. a and b always; c, d and e by pick. */
export const QUESTIONS: readonly Question[] = [
  {
    id: 'about',
    says: [
      'Let’s start with a little about you. Would you share your name, gender, age, height and weight?',
      'It helps me work out your BMI, so every suggestion fits you. Just say it — or type it.',
    ],
    chips: [],
    when: null,
  },
  {
    id: 'place',
    says: ['Where do you live, and what do you eat? Then the meals I suggest are ones you can get, and actually want.'],
    chips: ['Veg', 'Non-veg', 'Eggetarian', 'Anything'],
    when: null,
  },
  {
    id: 'health',
    says: ['What’s your health goal? Give me a number if there is one — like lose 5 kg.'],
    chips: ['Lose weight', 'Gain muscle', 'Eat cleaner'],
    when: 'health',
  },
  {
    id: 'money',
    says: ['How much do you want to save every month? I’ll keep your daily spending to what’s left after it.'],
    chips: [],
    when: 'money',
  },
  {
    id: 'habits',
    says: ['Which habits do you want to track?'],
    chips: ['Gym', 'Running', 'Sleep early', 'Fewer cigarettes'],
    when: 'habits',
  },
];

export const question = (id: OnboardingQuestion): Question => QUESTIONS.find((q) => q.id === id)!;

/** The questions the picks ask, in order. */
export const questionsFor = (picks: ReadonlySet<PickId>): Question[] =>
  QUESTIONS.filter((q) => q.when == null || picks.has(q.when));

/** The agent's one word for an answer it could not read. A second one moves on. */
export const AGAIN = 'Say that again?';

export const LINES = {
  done: 'That’s everything I need. Here’s your start.',
  nothing: 'You can tell me any of this later.',
  failed: 'I couldn’t take that in — try again?',
  /** Past the day's cap: said once, and the questions end on it. */
  capped: 'That’s all I can take in today. You can tell me the rest later.',
  undoFailed: 'That didn’t undo — try again?',
  allSet: (name: string) => (name ? `You’re all set, ${name}.` : 'You’re all set.'),
  headed: 'Here’s where you’re starting, and where you’re headed.',
  unread: 'I couldn’t read that back just now.',
} as const;

export const PLACEHOLDER = 'Say it, or type it…';
export const LISTENING = 'Listening…';
