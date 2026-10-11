import { color, font } from '../theme';
import type { ProjectStat } from '../types';

/** Bar area, in px. Everything else sizes off the labels. */
const BAR_H = 58;
const BAR_W = 20;

/**
 * Tasks per project — count up the y, one bar per project across the x.
 *
 * This replaced concentric arcs, which were wrong here on three counts: nested
 * rings read as a hierarchy that three sibling projects do not have; an arc's
 * length depends on its radius, so the same percentage looks bigger on the
 * outer ring than the inner one; and the component capped out at three radii.
 * Bars share a baseline, which is the strongest way to compare magnitudes, and
 * a fourth project just adds a column.
 *
 * Each bar is stacked — solid is finished, translucent is what is left — so one
 * mark carries both how much work a project holds and how far along it is. A
 * red pip sits above any project with something already overdue.
 */
export default function ProjectChart({ projects }: { projects: ProjectStat[] }) {
  const peak = Math.max(1, ...projects.map((p) => p.total));

  return (
    <div>
      <div
        style={{
          display: 'flex',
          gap: 10,
          justifyContent: 'center',
          alignItems: 'flex-end',
          height: BAR_H,
          borderBottom: `1px solid ${color.border}`,
        }}
        role="img"
        aria-label={projects
          .map((p) => `${p.name}: ${p.done} of ${p.total} done${p.late ? `, ${p.late} late` : ''}`)
          .join('. ')}
      >
        {projects.map((proj) => {
          const h = Math.round((proj.total / peak) * (BAR_H - 8));
          const fill = proj.total ? Math.round((proj.done / proj.total) * h) : 0;
          return (
            <div
              key={proj.id}
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 4,
                  height: 4,
                  borderRadius: '50%',
                  background: proj.late ? color.red : 'transparent',
                }}
              />
              <div
                style={{
                  width: BAR_W,
                  // An empty window still gets a stub, so the column and its
                  // label do not silently disappear from the axis.
                  height: Math.max(2, h),
                  borderRadius: '3px 3px 0 0',
                  background: `${proj.color}2E`,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'flex-end',
                  transition: 'height 0.45s cubic-bezier(0.4,0,0.2,1)',
                }}
              >
                <div
                  style={{
                    height: fill,
                    background: proj.color,
                    borderRadius: fill && fill >= h ? '3px 3px 0 0' : 0,
                    transition: 'height 0.45s cubic-bezier(0.4,0,0.2,1)',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 6 }}>
        {projects.map((proj) => (
          <div
            key={proj.id}
            title={`${proj.name} — ${proj.done}/${proj.total}`}
            style={{
              width: BAR_W,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
              lineHeight: 1,
            }}
          >
            {/* Initials, not names: a name would wrap or clip at this width,
                and the rows beside the chart spell each project out in full. */}
            <span
              style={{
                fontFamily: font.sans,
                fontWeight: 600,
                fontSize: 11,
                color: proj.color,
              }}
            >
              {proj.name.charAt(0).toUpperCase()}
            </span>
            <span style={{ fontFamily: font.sans, fontSize: 11, color: color.faint }}>
              {proj.done}/{proj.total}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
