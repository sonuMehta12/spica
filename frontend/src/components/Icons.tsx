import {
  ArrowRight,
  ArrowUp,
  Barbell,
  Broom,
  CircleNotch,
  DotsThreeVertical,
  Image as ImageGlyph,
  List,
  Microphone,
  SignOut,
  type Icon,
} from '@phosphor-icons/react';
import { color } from '../theme';

/**
 * The app's icons are Phosphor (MIT), not hand-drawn: Regular weight for
 * chrome, Fill for the tiny marks — a habit's coin, a project's icon — where
 * a stroke would collapse into a letter. These wrappers keep the call sites'
 * names and give every glyph its default size and colour in one place.
 */

interface IconProps {
  size?: number;
  stroke?: string;
}

export function MenuIcon({ size = 20, stroke = color.ink }: IconProps) {
  return <List size={size} color={stroke} aria-hidden />;
}

/**
 * Clear the view. A broom, not a bin: the thread is swept off the screen and
 * nothing is deleted — and not three lines either, which read as a filter.
 */
export function ClearIcon({ size = 20, stroke = color.ink }: IconProps) {
  return <Broom size={size} color={stroke} aria-hidden />;
}

/**
 * A button is busy. One gap in the ring so the rotation is visible — a full
 * circle spinning looks like a circle standing still.
 */
export function SpinnerIcon({ size = 18, stroke = color.muted }: IconProps) {
  return (
    <CircleNotch
      size={size}
      color={stroke}
      aria-hidden
      style={{ animation: 'spin 0.75s linear infinite' }}
    />
  );
}

export function KebabIcon({ size = 18, stroke = color.ink }: IconProps) {
  return <DotsThreeVertical size={size} color={stroke} weight="bold" aria-hidden />;
}

export function MediaIcon({ size = 20, stroke = color.muted }: IconProps) {
  return <ImageGlyph size={size} color={stroke} aria-hidden />;
}

export function SendIcon({ size = 18, stroke = color.white }: IconProps) {
  return <ArrowUp size={size} color={stroke} weight="bold" aria-hidden />;
}

export function MicIcon({ size = 20, stroke = color.white }: IconProps) {
  return <Microphone size={size} color={stroke} aria-hidden />;
}

/** A tool's glyph in the `+` tray or a section tile — the icon comes from its registry. */
export function ToolIcon({ icon: Glyph, size = 18, stroke = color.muted }: IconProps & { icon: Icon }) {
  return <Glyph size={size} color={stroke} aria-hidden />;
}

/** Hands the rest of the list to the agent. */
export function ArrowIcon({ size = 14, stroke = color.muted }: IconProps) {
  return <ArrowRight size={size} color={stroke} aria-hidden />;
}

/** Labels a row of workouts. Filled: a stroked dumbbell at 16px reads as a capital H. */
export function WorkoutIcon({ size = 16, stroke = color.muted }: IconProps) {
  return <Barbell size={size} color={stroke} weight="fill" aria-hidden />;
}

/** Sign out: the arrow leaves the frame, which is the whole message. */
export function SignOutIcon({ size = 16, stroke = color.red }: IconProps) {
  return <SignOut size={size} color={stroke} aria-hidden />;
}
