import {
  BookOpen,
  Briefcase,
  ChatCircle,
  Code,
  Flag,
  Globe,
  Heart,
  House,
  Leaf,
  Lightning,
  Money,
  Rocket,
  ShoppingCart,
  Star,
  User,
  Wrench,
  type Icon,
} from '@phosphor-icons/react';
import { color, font } from '../theme';
import type { Project } from '../types';

/**
 * A project's mark: an emoji, one of the app's own icons, or its first letter.
 *
 * Notion-style — the person picks either kind, and nothing is uploaded
 * (spec/done/projects.md). The keys here are the set the server accepts and
 * stores (`app/projects.py` ICONS) — they stay as they are, and each maps to a
 * Phosphor glyph at Fill weight, drawn in the project's own colour. A key it
 * does not know draws the letter, which is the contract, not an edge case.
 */
export const ICON_GLYPHS: Record<string, Icon> = {
  briefcase: Briefcase,
  code: Code,
  home: House,
  heart: Heart,
  book: BookOpen,
  cart: ShoppingCart,
  rocket: Rocket,
  star: Star,
  bolt: Lightning,
  leaf: Leaf,
  chat: ChatCircle,
  money: Money,
  globe: Globe,
  tool: Wrench,
  person: User,
  flag: Flag,
};

export const ICON_NAMES = Object.keys(ICON_GLYPHS);

interface Props {
  project: Pick<Project, 'name' | 'color' | 'icon'> | undefined;
  /** The mark's box, in px. */
  size?: number;
}

export default function ProjectIcon({ project, size = 16 }: Props) {
  const tint = project?.color ?? color.grey;
  const icon = project?.icon;
  const box = {
    width: size,
    height: size,
    flex: '0 0 auto' as const,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const Glyph = icon && icon.startsWith('icon:') ? ICON_GLYPHS[icon.slice(5)] : undefined;
  if (Glyph) {
    return (
      <span aria-hidden="true" style={box}>
        <Glyph size={size} weight="fill" color={tint} />
      </span>
    );
  }
  if (icon && !icon.startsWith('icon:')) {
    return (
      <span aria-hidden="true" style={{ ...box, fontSize: size * 0.85, lineHeight: 1 }}>
        {icon}
      </span>
    );
  }
  return (
    <span
      aria-hidden="true"
      style={{
        ...box,
        borderRadius: size * 0.28,
        background: tint,
        color: color.white,
        fontFamily: font.sans,
        fontWeight: 600,
        fontSize: size * 0.6,
        lineHeight: 1,
      }}
    >
      {(project?.name ?? '?').trim().charAt(0).toUpperCase()}
    </span>
  );
}
